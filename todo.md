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
- Figure out how to link/reference discovered_by column to display name in Grafana
- Try to locate nodes based on SNR
- Hosts seem to have different values (battery can be 10% different, creates 'ocilations' on graphs)
- Show only last gps location on map (need some if statement in flux)
- Map query fails if it can't make a difference between values (node needs to travel in search timeframe to appear)
- Support for usb and bt devices along with tcp
- Done: Handle new nodes in `old_data`