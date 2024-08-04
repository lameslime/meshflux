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
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from env import *


client = InfluxDBClient(
    url=INFLUXDB_HOST, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG, verify_ssl=INFLUXDB_VERIFYSSL
)  # InfluxDB client connection details
# data = []

# global data_fresh = False

def get_meshtastic_data(host):
    # Gets info from local node, edit the command so it can find meshtastic plugin
    send_attempts, count_attempts = 3, 0
    while count_attempts < send_attempts:
        try:
            cmd = ["python", "-m", "meshtastic", "--host", host, "--info"] 
            result = str(subprocess.run(cmd, stdout=subprocess.PIPE).stdout)
            return result
        except Exception as e:
            count_attempts = count_attempts + 1
            print(f'Get failed {count_attempts} times, reason {e}')
            time.sleep(10)
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
        print("JSON unparsable, maybe connection problem")
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
        print("JSON unparsable, maybe connection problem")
        exit()


def handle_missing_data(value, key):
    # Safely get the value or return None if the key is missing
    return value.get(key) if key in value else None

def check_pos_time_diff(new_timestamp, host, node, old_data):
    # old_data has to look like {host_id: node_data, ...}
    
    if host in old_data.keys():
        old_timestamp = old_data[host][node]["position"]["time"]
        # print(f'{new_timestamp}; {old_timestamp}')
        if new_timestamp != old_timestamp:
            print(f'{node} position timestamp different, including')
            return True
    else:
        print(f'No timestamp on {node}')
        return False

def prepare_node_data(node_data, own_data):
    all_nodes = []
    global first_pass
    global second_pass

    # Finds and sets variable for host node
    if INCLUDE_DISCOVERED_BY == True:
        for key, value in node_data.items():
            if handle_missing_data(value, "num") == handle_missing_data(own_data, "myNodeNum"):
                print(f'Own node ({value["num"]}) found in all nodes ({own_data["myNodeNum"]}), including id: {str(key)}')
                node_discovered_by = str(key)
        # second_pass will be empty in the 1st loop
        first_pass[node_discovered_by] = node_data

    # Main loop
    for key, value in node_data.items():
        # print(key)
        lastHeard = value.get("lastHeard", 0)
        cur_time = time.time()
        # print(f'Last heard: {lastHeard - (cur_time - TIME_OFFSET)}')

        if TIME_OFFSET == 0 or lastHeard > cur_time - TIME_OFFSET:  ### Check if the node is fresh
            # node_data = {}
            # node_data["measurement"] = "meshtastic_node"
            # node_data["tags"] = {}
            # node_data["tags"]["short_name"] = value["user"].get("shortName")
            # node_data["tags"]["id"] = str(key)
            # node_data["tags"]["mac_address"] = value["user"].get("macaddr")
            # node_data["tags"]["hw_model"] = value["user"].get("hwodel")
            # node_data["tags"]["is_licensed"] = value["user"].get("isLicensed")
            # node_data["fields"] = {}
            # node_data["fields"]["battery_level"] = int(value["deviceMetrics"].get("batteryLevel"))
            # node_data["fields"]["voltage"] = value["deviceMetrics"].get("voltage")
            # node_data["fields"]["channel_utilization"] = value["deviceMetrics"].get("channelUtilization")
            # node_data["fields"]["air_util_tx"] = value["deviceMetrics"].get("airUtilTx")
            # node_data["fields"]["uptime"] = int(value["deviceMetrics"].get("uptimeSeconds"))
            # node_data["fields"]["pos_longitude"] = value["position"].get("longitude")
            # node_data["fields"]["pos_latitude"] = value["position"].get("latitude")
            # node_data["fields"]["pos_altitude"] = value["position"].get("altitude")
            # node_data["fields"]["snr"] = float(value.get("snr"))

            node_data = {}
            node_data["measurement"] = INFLUXDB_MEASUREMENT

            user_data = value.get("user", {})
            device_metrics = value.get("deviceMetrics", {})
            position_data = value.get("position", {})
            
            node_data["tags"] = {}

            # Add tags only if values exist
            node_data["tags"]["id"] = str(key)  # Assuming key is always available
            
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
            if is_licensed is not None:
                node_data["fields"]["is_licensed"] = 1
            else:
                node_data["fields"]["is_licensed"] = 0

            battery_level = handle_missing_data(device_metrics, "batteryLevel")
            if battery_level is not None:
                node_data["fields"]["battery_level"] = int(battery_level)

            voltage = handle_missing_data(device_metrics, "voltage")
            if voltage is not None:
                node_data["fields"]["voltage"] = float(voltage)

            channel_utilization = handle_missing_data(
                device_metrics, "channelUtilization"
            )
            if channel_utilization is not None:
                node_data["fields"]["channel_utilization"] = float(channel_utilization)

            air_util_tx = handle_missing_data(device_metrics, "airUtilTx")
            if air_util_tx is not None:
                node_data["fields"]["air_util_tx"] = float(air_util_tx)

            uptime = handle_missing_data(device_metrics, "uptimeSeconds")
            if uptime is not None:
                node_data["fields"]["uptime"] = int(uptime)

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
    # # print(prepered_data)
    send_attempts, count_attempts = 3, 0
    while count_attempts < send_attempts:
        try:
            client.write_api(write_options=SYNCHRONOUS).write(bucket=INFLUXDB_DB, org=INFLUXDB_ORG, record=prepered_data, write_precision=WritePrecision.S)
            print(f'Sent nodes to influxdb')
            break
        except Exception as e:
            count_attempts = count_attempts + 1
            print(f'Send failed {count_attempts} times, reason {e}')
            time.sleep(10)

    # for removing fields whos type has changed due to different data format sent
    # client.delete_api().delete("2023-01-01T00:00:00Z", "2024-08-05T21:15:00Z", '_measurement=meshtastic_node', bucket=INFLUXDB_DB, org=INFLUXDB_ORG)
    

def list_old_nodes(old_nodes, new_nodes):
    # Data conversion happens inside function, then comparasion
    node_list = list(old_nodes.keys())
    for item in new_nodes:
        # print(f'new {item['tags']['id']} old {list(all_nodes.keys())}')
        if str(item['tags']['id']) in node_list:
            node_list.remove(item['tags']['id'])
            # print(item['tags']['id'])
    if len(node_list) != 0:
        print(f'Nodes {node_list} are too old, skipping them')

if __name__ == '__main__':
    # Initialize 2 empty dicts, 2nd one will be used for comapring difference
    first_pass = {}
    second_pass = None

    while True:
        for host in MESH_NODE_HOSTS:
            raw_data = get_meshtastic_data(host)
            if raw_data == None:
                continue

            own_data = get_meshtastic_own_data(raw_data)
            # print(own_data)
            
            all_nodes = get_meshtastic_nodes(raw_data)
            print(f'[{host}] Total of {len(all_nodes)} nodes found')
            # print(list(all_nodes.keys()))
            # print(all_nodes)            
            prepared_data = prepare_node_data(all_nodes, own_data)
            print(f'Total of {len(prepared_data)} nodes prepared')
            # print(prepared_data)

            
            # all_nodes is a disct, prepared data is array of dicts with formated data for influxdb
            list_old_nodes(all_nodes, prepared_data)
            
            if READ_ONLY == False:
                send_nodes_to_influxdb(prepared_data)
            else:
                continue
        # print(old_data)

        # Move new data to old data
        # NOTE: Python compares dictionary references by default. TLDR dict(first_pass) creates a new dictionary that is a shallow copy
        # this ensures that second_pass is updated to reflect the latest state of first_pass
        second_pass = dict(first_pass)

        print(f'Sleeping {COLLECT_INTERVAL}s')
        time.sleep(COLLECT_INTERVAL)

