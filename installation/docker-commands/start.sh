#!/bin/bash
# init
# =============================================
# SCRIPT COMMANDS
echo
echo "** Starting Hummingbot instance **"
echo
echo "=> List of stopped docker instances:"
docker ps --filter "status=exited"
echo
echo "Note: if there are no instances listed, your instance may already be running."
echo "      If your instance is running, use the ./connect.sh script."
echo
echo "=> Enter the name for the Hummingbot instance to start:"
echo "   (Press enter for default value: hummingbot-instance)"
read INSTANCE_NAME
if [ "$INSTANCE_NAME" == "" ];
then
  INSTANCE_NAME="hummingbot-instance"
fi
# =============================================
# EXECUTE SCRIPT
docker start $INSTANCE_NAME && docker attach $INSTANCE_NAME