"""
 * MeshFlux
 * Meshtastic Nodes to InfluxDB
 *
 * Created in 2024 by Martti
"""

import json
from json import JSONDecodeError
import os
import subprocess
import time
import re
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import logging
from colorlog import ColoredFormatter

# Secrets and settings
from env import *

logger = logging.getLogger()
logger.setLevel(getattr(logging, LOG_LEVEL.upper()))

handler = logging.StreamHandler() # Create a console handler
formatter = ColoredFormatter(
    "%(asctime)s | %(levelname)s: %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S',  # Basic date and time format
    style='%'
)

handler.setFormatter(formatter)
logger.addHandler(handler)

# InfluxDB client object
client = InfluxDBClient(url=INFLUXDB_HOST, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG, verify_ssl=INFLUXDB_VERIFYSSL)

def get_meshtastic_data(host):
    # Gets info from local node
    get_attempts, count_attempts = 3, 0
    fail_regex = "^b'Error connecting to.*(?=:)"
    success_regex = "^b'Connected to radio"
    while count_attempts < get_attempts:
        try:
            cmd = ["python", "-m", "meshtastic", "--host", host, "--info"] 
            result = str(subprocess.run(cmd, stdout=subprocess.PIPE).stdout)

            connection_success = re.search(success_regex, result)
            if connection_success is not None:
                return result
            
            # Not sure what kind of errors may arrive, so in exception it tries again 
            connection_error = re.search(fail_regex, result)
            if connection_error is not None:
                raise ValueError(connection_error.group()[2:])

        except Exception as e:
            count_attempts = count_attempts + 1
            logger.error(f'Get failed {count_attempts} times of {get_attempts}, reason "{e}"')
            time.sleep(10)
    logger.error(f"Skipping {host}'s data collection")
    return None
    
def get_meshtastic_own_data(raw_data):
    result = raw_data
    
    ### Clean up the results
    start_pos = result.find("My info:") + len("My info:")
    end_pos = result.find("Metadata: ")

    ### Get only the piece of data with node information
    json_chunk = result[start_pos:end_pos]

    ### Clean up the JSON before parsing
    json_chunk_fixed = json_chunk.replace("\\r", "")
    json_chunk_fixed = json_chunk_fixed.replace("\\n", "")

    try:
        parsed_json = json.loads(json_chunk_fixed)
        return parsed_json
    except JSONDecodeError:
        logger.critical("JSON unparsable, maybe connection problem")
        exit()

def get_meshtastic_nodes(raw_data):
    result = raw_data
    
    ### Clean up the results
    start_pos = result.find("Nodes in mesh: ") + len("Nodes in mesh: ")
    end_pos = result.find("Preferences:")

    ### Get only the piece of data with node information
    json_chunk = result[start_pos:end_pos]

    ### Clean up the JSON before parsing
    json_chunk_fixed = json_chunk.replace("\\r", "")
    json_chunk_fixed = json_chunk_fixed.replace("\\n", "")

    try:
        parsed_json = json.loads(json_chunk_fixed)
        return parsed_json
    except JSONDecodeError:
        logger.critical("JSON unparsable, maybe connection problem")
        exit()

def handle_missing_data(value, key):
    # Safely get the value or return None if the key is missing
    return value.get(key) if key in value else None

def check_pos_time_diff(new_timestamp, host, node, old_data):
    # Checks if position timestamp has changed 
    # old_data has to look like {host_id: node_data, ...}
    if host in old_data.keys():
        old_timestamp = old_data[host][node]["position"]["time"]
        # print(f'{new_timestamp}; {old_timestamp}')
        if new_timestamp != old_timestamp:
            logger.debug(f'{node} position timestamp different, including')
            return True
    else:
        logger.debug(f'No timestamp on {node}')
        return False

def prepare_node_data(node_data, own_data):
    all_nodes = []
    global first_pass
    global second_pass

    # Finds and sets variable for host node
    if INCLUDE_DISCOVERED_BY == True:
        for key, value in node_data.items():
            if handle_missing_data(value, "num") == handle_missing_data(own_data, "myNodeNum"):
                logger.debug(f'Own node ({value["num"]}) found in all nodes ({own_data["myNodeNum"]}), including id: {str(key)}')
                node_discovered_by = str(key)

        first_pass[node_discovered_by] = node_data # second_pass will be empty in the 1st loop

    # Main loop
    for key, value in node_data.items():
        # print(key)
        lastHeard = value.get("lastHeard", 0)
        cur_time = time.time()
        # logger.debug(f'Last heard: {lastHeard - (cur_time - TIME_OFFSET)}')

        if TIME_OFFSET == 0 or lastHeard > cur_time - TIME_OFFSET:  ### Check if the node is fresh
            node_data = {}
            node_data["measurement"] = INFLUXDB_MEASUREMENT

            user_data = value.get("user", {})
            device_metrics = value.get("deviceMetrics", {})
            position_data = value.get("position", {})
            
            node_data["tags"] = {}
            node_data["tags"]["id"] = str(key)  # Assuming key is always available
            
            # Add values only if values exist
            short_name = handle_missing_data(user_data, "shortName")
            if short_name is not None:
                node_data["tags"]["short_name"] = str(short_name)

            long_name = handle_missing_data(user_data, "longName")
            if long_name is not None:
                node_data["tags"]["long_name"] = str(long_name)

            mac_address = handle_missing_data(user_data, "macaddr")
            if mac_address is not None:
                node_data["tags"]["mac_address"] = str(mac_address)

            hw_model = handle_missing_data(user_data, "hwModel")
            if hw_model is not None:
                node_data["tags"]["hw_model"] = str(hw_model)

            if node_discovered_by is not None:
                node_data["tags"]["discovered_by"] = str(node_discovered_by)

            node_data["fields"] = {}
            
            is_licensed = handle_missing_data(user_data, "isLicensed")
            if is_licensed is not None: # Can't be bool, Influx doesn't like it in filters/agregation
                node_data["fields"]["is_licensed"] = 1
            else:
                node_data["fields"]["is_licensed"] = 0

            battery_level = handle_missing_data(device_metrics, "batteryLevel")
            if battery_level is not None:
                node_data["fields"]["battery_level"] = int(battery_level)

            voltage = handle_missing_data(device_metrics, "voltage")
            if voltage is not None:
                node_data["fields"]["voltage"] = float(voltage)

            channel_utilization = handle_missing_data(device_metrics, "channelUtilization")
            if channel_utilization is not None:
                node_data["fields"]["channel_utilization"] = float(channel_utilization)

            air_util_tx = handle_missing_data(device_metrics, "airUtilTx")
            if air_util_tx is not None:
                node_data["fields"]["air_util_tx"] = float(air_util_tx)

            uptime = handle_missing_data(device_metrics, "uptimeSeconds")
            if uptime is not None:
                node_data["fields"]["uptime"] = int(uptime)

            # Only is set if timestamp is different
            pos_time = handle_missing_data(position_data, "time")
            if pos_time is not None and second_pass is not None:
                if check_pos_time_diff(pos_time, node_discovered_by, key, second_pass):
                    node_data["fields"]["pos_time"] = datetime.fromtimestamp(pos_time, tz=timezone.utc).isoformat()

                pos_longitude = handle_missing_data(position_data, "longitude")
                if pos_longitude is not None:
                    node_data["fields"]["pos_longitude"] = float(pos_longitude)

                pos_latitude = handle_missing_data(position_data, "latitude")
                if pos_latitude is not None:
                    node_data["fields"]["pos_latitude"] = float(pos_latitude)

                pos_altitude = handle_missing_data(position_data, "altitude")
                if pos_altitude is not None:
                    node_data["fields"]["pos_altitude"] = float(pos_altitude)
            
            last_heard = handle_missing_data(value, "lastHeard")
            if last_heard is not None:
                node_data["fields"]["last_heard"] = datetime.fromtimestamp(last_heard, tz=timezone.utc).isoformat()

            snr = handle_missing_data(value, "snr")
            if snr is not None:
                node_data["fields"]["snr"] = float(snr)

            role = handle_missing_data(user_data, "role")
            if role is not None:
                node_data["fields"]["role"] = str(role)
            
            all_nodes.append(node_data)
    return all_nodes


def send_nodes_to_influxdb(prepered_data):
    # print(prepered_data)
    send_attempts, count_attempts = 3, 0
    while count_attempts < send_attempts:
        try:
            client.write_api(write_options=SYNCHRONOUS).write(bucket=INFLUXDB_DB, org=INFLUXDB_ORG, record=prepered_data, write_precision=WritePrecision.S)
            logger.info(f'Sent nodes to influxdb')
            break
        except Exception as e:
            count_attempts = count_attempts + 1
            logger.critical(f'Send failed {count_attempts} times, reason {e}')
            time.sleep(10)

    # For removing fields who's type has changed due to different data format sent
    # client.delete_api().delete("2023-01-01T00:00:00Z", "2024-08-05T21:15:00Z", f'_measurement={INFLUXDB_MEASUREMENT}', bucket=INFLUXDB_DB, org=INFLUXDB_ORG)
    
def list_old_nodes(old_nodes, new_nodes):
    # Data conversion happens inside function, then comparasion
    node_list = list(old_nodes.keys())
    for item in new_nodes:
        # print(f'new {item['tags']['id']} old {list(all_nodes.keys())}')
        if str(item['tags']['id']) in node_list:
            node_list.remove(item['tags']['id'])
    if len(node_list) != 0:
        logger.debug(f'Nodes {node_list} are too old, skipping them')

if __name__ == '__main__':
    # Initialize 2 empty dicts, 2nd one will be used for comapring difference
    first_pass = {}
    second_pass = None

    while True:
        for host in MESH_NODE_HOSTS:
            raw_data = get_meshtastic_data(host)
            if raw_data == None:
                continue

            own_data = get_meshtastic_own_data(raw_data) # own_data is a dict
            # print(own_data)
            
            all_nodes = get_meshtastic_nodes(raw_data) # all_nodes is a dict
            logger.info(f'[{host}] Total of {len(all_nodes)} nodes found')
            # print(all_nodes) 
           
            prepared_data = prepare_node_data(all_nodes, own_data) # prepared_data is array of dicts (all_nodes) with formated data for influxdb
            logger.info(f'Total of {len(prepared_data)} nodes prepared')
            # print(prepared_data)

            list_old_nodes(all_nodes, prepared_data)
            
            if READ_ONLY == False:
                send_nodes_to_influxdb(prepared_data)
            else:
                continue

        # Move new data to old data
        # NOTE: Python compares dictionary references by default. TLDR dict(first_pass) creates a new dictionary that is a shallow copy
        # this ensures that second_pass is updated to reflect the latest state of first_pass
        second_pass = dict(first_pass)

        logger.info(f'Sleeping {COLLECT_INTERVAL}s\n')
        time.sleep(COLLECT_INTERVAL)

