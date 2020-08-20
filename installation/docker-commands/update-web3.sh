#!/bin/bash
# init
# =============================================
# SCRIPT COMMANDS
echo
echo "** 🔄  Update Hummingbot instance **"
echo
echo "🚫  List of running docker instances:"
docker ps
echo
echo "🚫  If your instance is still running, connect to your instance and run \"exit\" to shut down prior to updating."
echo
echo "✅  List of stopped docker instances:"
docker ps --filter "status=exited"
echo
echo "✅  stopped instances can be updated."
echo
# Specify hummingbot version
echo "ℹ️  Press [enter] for default values."
echo
echo "➡️  Enter hummingbot version to update: [latest|development] (default = \"latest\")"
read TAG
if [ "$TAG" == "" ]
then
  TAG="latest"
fi
echo
# Initialize loop
i="0"
declare -a INSTANCES
declare -a FOLDERS
CONTINUE="Y"
while [ "$CONTINUE" == "Y" ]
do
  # Ask the user for the name of the instance to update
  echo "➡️  Enter the name of the Hummingbot instance to update: (default = \"hummingbot-instance\")"
  read INSTANCE_NAME
  if [ "$INSTANCE_NAME" == "" ];
  then
    INSTANCE_NAME="hummingbot-instance"
    DEFAULT_FOLDER="hummingbot_files"
  else
    DEFAULT_FOLDER="${INSTANCE_NAME}_files"
  fi
  # Add instance name to array
  INSTANCES[$i]=$INSTANCE_NAME
  echo
  echo "=> Instance name: $INSTANCE_NAME"
  echo
  # List all directories in the current folder
  echo "📁 List of folders in your directory:"
  ls -d */
  echo
  # Ask the user for the folder location of the instance
  echo "➡️  Enter a folder for your config and log files: (default = \"$DEFAULT_FOLDER\")"
  read FOLDER
  if [ "$FOLDER" == "" ]
  then
    FOLDER=$DEFAULT_FOLDER
  fi
  # Add folder to array
  FOLDERS[$i]=$FOLDER
  echo "➡️  Update an additional image? [Y/N] (default = N)"
  read CONTINUE
  if [ "$CONTINUE" == "Y" ]
  then
    i=$[$i+1]
  fi
  echo
done
#
#
#
# =============================================
# EXECUTE SCRIPT
echo
echo "Hummingbot version: coinalpha/hummingbot:$TAG"
echo "List of instances to be updated:"
j="0"
while [ $j -le $i ]
do
  echo "$[$j+1]) ${INSTANCES[$j]}: $(pwd)/${FOLDERS[$j]}"
  j=$[$j+1]
done
echo
echo "➡️  Verify the instances and folders above.  To proceed, enter \"Yes\" (default = \"No\")"
read PROCEED
if [ "$PROCEED" == "Yes" ]
then
  # 1) Delete instance and old hummingbot image
  j="0"
  while [ $j -le $i ]
  do
    docker rm ${INSTANCES[$j]}
    j=$[$j+1]
  done
  # 2) Delete old image
  docker image rm coinalpha/hummingbot:$TAG
  # 3) Re-create instances with latest hummingbot release
  j="0"
  while [ $j -le $i ]
  do
    docker run -itd \
    --network host \
    --name ${INSTANCES[$j]} \
    --mount "type=bind,source=$(pwd)/${FOLDERS[$j]}/hummingbot_conf,destination=/conf/" \
    --mount "type=bind,source=$(pwd)/${FOLDERS[$j]}/hummingbot_logs,destination=/logs/" \
    --mount "type=bind,source=$(pwd)/${FOLDERs[$j]}/hummingbot_data,destination=/data/" \
    --mount "type=bind,source=$(pwd)/${FOLDERS[$j]}/hummingbot_scripts,destination=/scripts/" \
    coinalpha/hummingbot:$TAG
    j=$[$j+1]
  done
  echo
  echo "🏁 Update complete! Current instances:"
  docker ps
  echo
  echo "Run ./start.sh to connect to an instance."
else
  echo "Update aborted"
fi
