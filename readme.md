## What is it
Basically
- Reads data from Meshtastic device
- Formats data
- Sends to InfluxDB

But also
- Allows multiple devices to send info and filter based on it
- Group devices by name, mac and hardware

## What it monitors
- Everything in nodes tab

## Why
MQTT isn't meant for long term storage and it's harder to visualize

[<img src="./grafana/grafana-dashboard.jpeg">]()

## Setup
- Make sure you have a 
  - Working python install (tested 3.12.3)
    - And required modules (pip install -r requirements.txt)
  - InfluxDB v2
    - With a bucket and token
  - Grafana (and InfluxDB as data source)
- Rename env.py.example to env.py and fill in
- Possibly edit cmd variable in get_meshtastic_data function (main.py)
- Import Grafana dashboard (you also need official GeoMap plugin)
- Run and wait for data

or skip having a python install and use a docker container
- git clone https://github.com/lameslime/meshflux
- copy env.py.example to env.py and fill in
- docker compose up --build -d

## Note
I happened to make it on Windows, there should be no problems on linux (check cmd variable)

It is confirmed working with RAK4631 using PoE, you can edit cmd variable to use bt or usb

## TODO and sort of a buglist
Left are qol changes, some are easier, others I don't want to spend time on
- Done: Docker image
- Done: Hopefully have a heatmap layer on map displaying signal strength
- Done: INCLUDE_DISCOVERED_BY functionality in grafana  
If enabled then it will create duplicate names in 'basic' queries, because if you use multiple nodes to ingest data to the same bucket fields will be different.
Additional logic will be needed in flux queries, to ignore/filter based on ingestors id.
- Done: Error handling (Meshtasic and InfluxDB timeouts); Super basic 3 tries and still continues
- Done: Multiple Meshtastic nodes
- Done: Data deduplication (GPS data gets outdated fast)
- Filter out garbage position data (too big changes, eg node is indoors and gps is innaccurate, like in the screenshot)
- Maybe apply deduplication elsewhere (need dynamic way)
- Figure out how to link/reference discovered_by to display name in Grafana
- Try to locate nodes based on SNR
- Hosts seem to have different values (battery can be 10% different, creates 'ocilations' on graphs)
- Show only last gps location on map (need some if statement in flux)
- Map query fails if it can't make a difference between values (node needs to travel in search timeframe to appear)

## Credits
Dmitri Prigojev for inspiration
https://github.com/dmitripr/meshtastic_InfluxDB

## License
Use it as you want, but I'd like to be listed in credits
