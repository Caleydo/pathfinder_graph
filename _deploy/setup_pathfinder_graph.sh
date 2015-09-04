#!/usr/bin/env bash

#search for the right parent directory such that we have a common start directory
while [[ ! -f "run.sh" ]] && [[ ! -f "Vagrantfile" ]]
do
  cd ..
done


mkdir -p _data/
cd _data
basedir=`pwd`

baseurl="https://googledrive.com/host/0B7lah7E3BqlAfmNnQ3ptNUhtbG1fWklkemVGc0xnZkNyZ21lUi15aFlIb3NSZ2FWOTR3NHM/"
pluginname="neo4j-k-shortest-paths-plugin-2.2.3-SNAPSHOT.jar"

dbprefix="/home/`whoami`/neo4j_"

function sedeasy {
  sed -i "s/$(echo $1 | sed -e 's/\([[\/.*]\|\]\)/\\&/g')/$(echo $2 | sed -e 's/[\/&]/\\&/g')/g" $3
}

function fixplugin {
  local dbdir=$1
  if [ ! -e ${pluginname} ] ; then
    #download if not existing
    wget --timestamping -O ${pluginname} "${baseurl}/${pluginname}"
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

function updateplugin {
  #download if not existing
  wget --timestamping -O ${pluginname} "${baseurl}/${pluginname}"
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
  chown -R `whoami` ${db}d/data/graph.db
}

function managedb {
  local name=${1:-vis}
  local db=${dbprefix}${name}
  local cmd=${2:-stop}

  (exec ${db} ${cmd})
}

function uninstalldb {
  local name=${1:-vis}
  local db=${dbprefix}${name}

  managedb ${name} stop
  rm -rf ${db}d
}

function setup {
  createdb dblp 7474
  createdb pathways 7475
  createdb dot 7476
}

function update {
  updateplugin
  #no data update yet
  managedb dblp restart
  managedb pathways restart
  managedb dot restart
}

function uninstall {
  uninstalldb dblp
  uninstalldb pathways
  uninstalldb pathways

  #remove plugin
  rm -f "${baseurl}/${pluginname}"
}

#command switch
case "$1" in
update)
  update
  ;;
uninstall)
  uninstall
  ;;
*)
  setup
  ;;
esac