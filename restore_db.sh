#!/usr/bin/env bash
echo stopping neo4j database service
sudo service neo4j-service stop

if [ -z "$1" ]
then 
    if [ -d "/var/lib/neo4j/data/backup/" ]
    then
        echo restoring db from /var/lib/neo4j/data/backup/
        sudo rm -rf /var/lib/neo4j/data/graph.db
        sudo mkdir -p /var/lib/neo4j/data/graph.db
        sudo cp -a /var/lib/neo4j/data/backup/. /var/lib/neo4j/data/graph.db
    else
        echo default backup folder does not exist and no backup folder specified
    fi
else
    echo restoring db from $1
    sudo rm -rf /var/lib/neo4j/data/graph.db
    sudo mkdir -p /var/lib/neo4j/data/graph.db
    sudo mkdir -p $1
    sudo cp -a $1/. /var/lib/neo4j/data/graph.db/
fi

echo restarting neo4j database service
sudo service neo4j-service start