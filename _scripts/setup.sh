#!/usr/bin/env bash

function ensure_in_vm {
  if [ "`whoami`" != "vagrant" ] ; then
    echo "this command should be executed within the VM: aborting"
    exit 1
  fi
}

ensure_in_vm

#search for the right parent directory
while [ ! -f "Vagrantfile" ]
do
  cd ..
done

mkdir -p _data/
cd _data
basedir=`pwd`

baseurl="https://googledrive.com/host/0B7lah7E3BqlAfmNnQ3ptNUhtbG1fWklkemVGc0xnZkNyZ21lUi15aFlIb3NSZ2FWOTR3NHM/"

dbprefix="/home/vagrant/neo4j_"

function sedeasy {
  sed -i "s/$(echo $1 | sed -e 's/\([[\/.*]\|\]\)/\\&/g')/$(echo $2 | sed -e 's/[\/&]/\\&/g')/g" $3
}

function fixplugin {
  local dbdir=$1
  local pluginname="neo4j-k-shortest-paths-plugin-2.2.3-SNAPSHOT.jar"
  if [ ! -e ${pluginname} ] ; then
    #download if not existing
    wget -O ${pluginname} "${baseurl}/${pluginname}"
  fi

  #create the link to the plugin itself
  if [ ! -e "${dbdir}/plugins/${pluginname}" ] ; then
    #remove the shared link and create a real one
    rm -r ${dbdir}/plugins
    mkdir -p ${dbdir}/plugins
    ln -s "${basedir}/${pluginname}" "${dbdir}/plugins/"
  fi

  #change the config file
  sedeasy "#org.neo4j.server.thirdparty_jaxrs_classes=org.neo4j.examples.server.unmanaged=/examples/unmanaged" "org.neo4j.server.thirdparty_jaxrs_classes=org.caleydo.neo4j.plugins.kshortestpaths=/caleydo" ${dbdir}/conf/neo4j-server.properties
}

function createdb {
  local name=${1:-vis}
  local port=${2:-7475}
  local db=${dbprefix}${name}
  if [ -d ${db}d ] ; then
    return 0
  fi
  #clone db
  ../scripts/clone_neo4j.sh ${name} ${port}

  #fix plugin setting
  fixplugin ${db}d

  #download the data
  local datafile="neo4j_${name}.tar.gz"
  if [ ! -e ${datafile} ] ; then
    #download if not existing
    wget -O ${datafile} "${baseurl}/${datafile}"
  fi
  #unzip
  mkdir -p "${db}d/data/graph.db"
  tar -xzf ${datafile} -C "${db}d/data/graph.db"
  #fix permissions
  chown -R vagrant:vagrant ${db}d/data/graph.db
}

createdb dblp 7474
createdb pathways 7475
createdb dot 7476
