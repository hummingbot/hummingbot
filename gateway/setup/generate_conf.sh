#!/bin/bash
# init

echo
echo
echo "===============  GENERATE GATEWAY CONFIGURATION FILES ==============="
echo
echo


HOST_CONF_PATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../conf"

TEMPLATE_DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates"

echo "HOST_CONF_PATH=$HOST_CONF_PATH"

mkdir $HOST_CONF_PATH

# copy the following files

cp $TEMPLATE_DIR/**.yml $HOST_CONF_PATH
echo "All configuration files have been created."