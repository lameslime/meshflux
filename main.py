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
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from env import *


client = InfluxDBClient(
    url=INFLUXDB_HOST, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG, verify_ssl=INFLUXDB_VERIFYSSL
)  # InfluxDB client connection details
# data = []

# global data_fresh = False

def get_meshtastic_data():
    # Gets info from local node, edit the command so it can find meshtastic plugin
    cmd = ["python", "-m", "meshtastic", "--host", MESH_NODE_HOST, "--info"] 
    result = str(subprocess.run(cmd, stdout=subprocess.PIPE).stdout)
    return result

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


def prepare_node_data(node_data, own_data):
    all_nodes = []

    # Finds and sets variable for host node
    if INCLUDE_DISCOVERED_BY == True:
        for key, value in node_data.items():
            if handle_missing_data(value, "num") == handle_missing_data(own_data, "myNodeNum"):
                print(f'Own node ({value["num"]}) found in all nodes ({own_data["myNodeNum"]}), including id: {str(key)}')
                node_discovered_by = str(key)

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
                node_data["tags"]["discovered_by"] = node_discovered_by

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
                node_data["fields"]["voltage"] = voltage

            channel_utilization = handle_missing_data(
                device_metrics, "channelUtilization"
            )
            if channel_utilization is not None:
                node_data["fields"]["channel_utilization"] = channel_utilization

            air_util_tx = handle_missing_data(device_metrics, "airUtilTx")
            if air_util_tx is not None:
                node_data["fields"]["air_util_tx"] = air_util_tx

            uptime = handle_missing_data(device_metrics, "uptimeSeconds")
            if uptime is not None:
                node_data["fields"]["uptime"] = int(uptime)

            pos_longitude = handle_missing_data(position_data, "longitude")
            if pos_longitude is not None:
                node_data["fields"]["pos_longitude"] = pos_longitude

            pos_latitude = handle_missing_data(position_data, "latitude")
            if pos_latitude is not None:
                node_data["fields"]["pos_latitude"] = pos_latitude

            pos_altitude = handle_missing_data(position_data, "altitude")
            if pos_altitude is not None:
                node_data["fields"]["pos_altitude"] = pos_altitude

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
    client.write_api(write_options=SYNCHRONOUS).write(bucket=INFLUXDB_DB, org=INFLUXDB_ORG, record=prepered_data, write_precision=WritePrecision.S)
    
    # for removing fields whos type has changed due to different data format sent
    # client.delete_api().delete("2023-01-01T00:00:00Z", "2024-08-03T21:15:00Z", '_measurement=meshtastic_node' ,bucket=INFLUXDB_DB, org=INFLUXDB_ORG)
    print(f'Sent nodes to influxdb')


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
    while True:
        raw_data = get_meshtastic_data()
        
        own_data = get_meshtastic_own_data(raw_data)
        # print(own_data)
        
        all_nodes = get_meshtastic_nodes(raw_data)
        print(f'Total of {len(all_nodes)} nodes found')
        print(list(all_nodes.keys()))
        # print(all_nodes)
        
        prepared_data = prepare_node_data(all_nodes, own_data)
        print(f'Total of {len(prepared_data)} nodes prepared')
        # print(prepared_data)
        
        # all_nodes is a disct, prepared data is array of dicts with formated data for influxdb
        list_old_nodes(all_nodes, prepared_data)
        
        if READ_ONLY == False:
            send_nodes_to_influxdb(prepared_data)
        else:
            print(prepared_data)
            exit()
        print(f'Sleeping {COLLECT_INTERVAL}s')
        
        time.sleep(COLLECT_INTERVAL)
