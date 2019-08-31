#!/bin/bash
# init
# =============================================
# SCRIPT COMMANDS
echo
echo "** Load Hummingbot instance **"
echo
echo "=> List of docker instances:"
docker ps -a
echo
echo "➡️  Enter the name for the Hummingbot instance to connect to:"
echo "   (Press enter for default value: hummingbot-instance)"
read INSTANCE_NAME
if [ "$INSTANCE_NAME" == "" ];
then
  INSTANCE_NAME="hummingbot-instance"
fi
# =============================================
# EXECUTE SCRIPT
docker start $INSTANCE_NAME && docker attach $INSTANCE_NAME