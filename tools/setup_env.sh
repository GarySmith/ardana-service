#!/bin/bash

# Gotta be somewhere in the tree to run this
git rev-parse || exit

cd $(git rev-parse --show-toplevel)

GIT_BASE=${GIT_BASE:-https://git.suse.provo.cloud}
SCRIPT=setup-ardana-cp.sh

# Create dirs for customer data, scratch area
mkdir -p \
   data/my_cloud/model \
   data/my_cloud/config \
   data/scratch \
   data/cp/output \
   data/cp/ready \
   log

cd data

if [ ! -d my_cloud/.git ] ; then
    cd my_cloud
    git init 
    git commit --allow-empty -m "Initial commit"
    git checkout -b site
    cd -
fi

if [ ! -d ardana-ansible ] ; then
    git clone ${GIT_BASE}/ardana/ardana-ansible
fi

if [ ! -d ardana-input-model ] ; then
    git clone ${GIT_BASE}/ardana/ardana-input-model
fi

# Setup config processor.  This process basically automates the steps needed to
#    create a development environment for the config processor
if [ ! -d config-processor ] ; then
    if [ ! -f $SCRIPT ] ; then
        curl -k ${GIT_BASE}/cgit/ardana/ardana-configuration-processor/plain/Scripts/$SCRIPT > $SCRIPT
        chmod +x $SCRIPT
    fi

    # Specify a directory for the config processor and the repos it needs
    DEST=config-processor

    # Prepare the dir for development, including checking out needed repos
    ./$SCRIPT -n $DEST

    # Prepare a virtual environment
    virtualenv -p /usr/bin/python2.7 $DEST
    VENV=$PWD/$DEST

    # upgrade the local version of pip in case the venv installed an old one
    $VENV/bin/pip install --upgrade pip

    # Install pre-reqs into the virtual environment
    $VENV/bin/pip install -r $DEST/ardana-configuration-processor/ConfigurationProcessor/requirements.txt

    # Install the config processor plugins into the python environment
    cd $DEST/ardana-configuration-processor/ConfigurationProcessor
    $VENV/bin/python setup.py install
fi
