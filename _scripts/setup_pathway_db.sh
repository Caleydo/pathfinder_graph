#!/usr/bin/env bash
echo stopping neo4j database service
sudo service neo4j-service stop

echo removing existing database
sudo rm -rf /var/lib/neo4j/data/graph.db

echo restarting neo4j database service
sudo service neo4j-service start

#echo executing kegg importer
#python kegg_importer_no_sets.py

