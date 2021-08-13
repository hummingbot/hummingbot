#!/bin/bash
# init
# =============================================

# Specify hummingbot version
select_version () {
 echo
 echo
 echo "===============  UPDATE HUMMINGBOT INSTANCE ==============="
 echo
 echo
 echo "ℹ️  Press [ENTER] for default values:"
 echo
 read -p "   Enter Hummingbot version to update [latest/development] (default = \"latest\") >>> " TAG
 if [ "$TAG" == "" ]
 then
   TAG="latest"
 fi
}

# List all docker instances using the same image
list_instances () {
 echo
 echo "List of all docker containers using the \"$TAG\" version:"
 echo
 docker ps -a --filter ancestor=coinalpha/hummingbot:$TAG
 echo
 echo "⚠️  WARNING: This will attempt to update all instances. Any containers not in Exited () STATUS will cause the update to fail."
 echo
 echo "ℹ️  TIP: Connect to a running instance using \"./start.sh\" command and \"exit\" from inside Hummingbot."
 echo "ℹ️  TIP: You can also remove unused instances by running \"docker rm [NAME]\" in the terminal."
 echo
 read -p "   Do you want to continue? [Y/N] >>> " CONTINUE
 if [ "$CONTINUE" == "" ]
 then
  CONTINUE="Y"
 fi
}

# List all directories in the current folder
list_dir () {
 echo
 echo "   List of folders in your directory:"
 echo
 ls -d1 */ 2>&1 | sed 's/^/   📁  /'
 echo
}

# Ask the user for the folder location of each instance
prompt_folder () {
 for instance in "${INSTANCES[@]}"
 do
   if [ "$instance" == "hummingbot-instance" ]
   then
     DEFAULT_FOLDER="hummingbot_files"
   else
     DEFAULT_FOLDER="${instance}_files"
   fi
   read -p "   Enter the destination folder for $instance (default = \"$DEFAULT_FOLDER\") >>> " FOLDER
   if [ "$FOLDER" == "" ]
   then
     FOLDER=$PWD/$DEFAULT_FOLDER
   elif [[ ${FOLDER::1} != "/" ]]; then
     FOLDER=$PWD/$FOLDER
   fi
   # Store folder names into an array
   FOLDERS+=($FOLDER)
 done
}

# Display instances and destination folders then prompt to proceed
confirm_update () {
 echo
 echo "ℹ️  Confirm below if the instances and their folders are correct:"
 echo
 num="0"
 printf "%30s %5s %10s\n" "INSTANCE" "         " "FOLDER"
 for instance in "${INSTANCES[@]}"
 do
   printf "%30s %5s %10s\n" ${INSTANCES[$num]} " ----------> " ${FOLDERS[$num]}
   num=$[$num+1]
 done
 echo
 read -p "   Proceed? [Y/N] >>> " PROCEED
 if [ "$PROCEED" == "" ]
 then
  PROCEED="Y"
 fi
}

# Execute docker commands
execute_docker () {
 # 1) Delete instance and old hummingbot image
 echo
 echo "Removing docker containers first ..."
 docker rm ${INSTANCES[@]}
 echo
 # 2) Delete old image
 docker image rm coinalpha/hummingbot:$TAG
 # 3) Re-create instances with the most recent hummingbot version
 echo "Re-creating docker containers with updated image ..."
 j="0"
 for instance in "${INSTANCES[@]}"
 do
   docker run -itd --log-opt max-size=10m --log-opt max-file=5 \
   --network host \
   --name ${INSTANCES[$j]} \
   --mount "type=bind,source=${FOLDERS[$j]}/hummingbot_conf,destination=/conf/" \
   --mount "type=bind,source=${FOLDERS[$j]}/hummingbot_logs,destination=/logs/" \
   --mount "type=bind,source=${FOLDERS[$j]}/hummingbot_data,destination=/data/" \
   --mount "type=bind,source=${FOLDERS[$j]}/hummingbot_scripts,destination=/scripts/" \
   --mount "type=bind,source=${FOLDERS[$j]}/hummingbot_certs,destination=/certs/" \
   coinalpha/hummingbot:$TAG
   j=$[$j+1]
 done
 echo
 echo "Update complete! All running docker instances:"
 echo
 docker ps
 echo
 echo "ℹ️  Run command \"./start.sh\" to connect to an instance."
 echo
}

select_version
list_instances
if [ "$CONTINUE" == "Y" ]
then
 # Store instance names in an array
 declare -a INSTANCES
 INSTANCES=( $(docker ps -a --filter ancestor=coinalpha/hummingbot:$TAG --format "{{.Names}}") )
 list_dir
 declare -a FOLDERS
 prompt_folder
 confirm_update
 if [ "$PROCEED" == "Y" ]
 then
   execute_docker
 else
   echo "   Update aborted"
   echo
 fi
else
  echo "   Update aborted"
  echo
fi
