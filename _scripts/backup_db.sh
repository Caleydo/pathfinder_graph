#!/usr/bin/env bash
echo stopping neo4j database service
sudo service neo4j-service stop

if [ -z "$1" ]
then 
    echo copying db to /var/lib/neo4j/data/backup/
    sudo mkdir -p /var/lib/neo4j/data/backup
    sudo rm -rf /var/lib/neo4j/data/backup
    sudo cp -a /var/lib/neo4j/data/graph.db/. /var/lib/neo4j/data/backup/
else
    echo copying db to $1
    sudo mkdir -p $1
    sudo cp -a /var/lib/neo4j/data/graph.db/. $1
fi

echo restarting neo4j database service
sudo service neo4j-service start