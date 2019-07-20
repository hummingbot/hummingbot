#!/bin/bash
# init
# =============================================
# SCRIPT COMMANDS
echo
echo "** Connecting to Hummingbot instance **"
echo
echo "=> List of running docker instances:"
docker ps
echo
echo "Note: if there are no instances listed, you do not have any running instances."
echo
echo "=> Enter the name of the Hummingbot instance to connect to:"
echo "   (Press enter for default value: hummingbot-instance)"
read INSTANCE_NAME
if [ "$INSTANCE_NAME" == "" ];
then
  INSTANCE_NAME="hummingbot-instance"
fi
# =============================================
# EXECUTE SCRIPT
docker attach $INSTANCE_NAME