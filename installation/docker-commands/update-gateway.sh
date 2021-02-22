#!/bin/bash
# init
# =============================================

# Specify hummingbot version
select_version () {
 echo
 echo
 echo "===============  UPDATE GATEWAY INSTANCE ==============="
 echo
 echo
 echo "ℹ️  Press [ENTER] for default values:"
 echo
 read -p "   Enter Gateway version to update [latest/development] (default = \"latest\") >>> " TAG
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
 docker ps -a --filter ancestor=coinalpha/gateway-api:$TAG
 echo
}


# Execute docker commands
execute_docker () {
 

 if [ ! "$INSTANCE_NAME" == "" ]
 then
  # 1) Delete instance and old gateway-api image
  echo
  echo "Stopping container: $INSTANCE_NAME"
  docker stop $INSTANCE_NAME
  echo "Removing container: $INSTANCE_NAME"
  docker rm $INSTANCE_NAME
  echo
 fi

 echo
 read -p "   Proceed with update? [Y/N] >>> " PROCEED
 if [[ ! "$PROCEED" == "Y" && ! "$PROCEED" == "y" ]]
 then
  echo "Abort"
  exit
 fi


 # 2) Delete old image
 echo
 read -p "   Delete current docker image coinalpha/gateway-api:$TAG? [Y/N] >>> " DELETE_IMAGE
 if [[ "$DELETE_IMAGE" == "Y" || "$DELETE_IMAGE" == "y" ]]
 then
  echo
  echo "Deleting old image: coinalpha/gateway-api:$TAG"
  docker image rm coinalpha/gateway-api:$TAG
  echo
 fi

 
 #3 ) Pull docker image
 echo
 read -p "   Pulling docker image coinalpha/gateway-api:$TAG [Y/N] >>> " PULL_IMAGE
 if [[ "$PULL_IMAGE" == "Y" || "$PULL_IMAGE" == "y" ]]
 then
  docker pull coinalpha/gateway-api:$TAG
  echo
 fi

 # 4) Re-create instances with the most recent hummingbot version
 echo
 echo "   Re-creating docker containers with updated image ..."

 ./create-gateway.sh

 echo
 echo "   Listing current running docker instances"
 docker ps
 echo
 echo
}


select_version

# get container instances
list_instances

# Ask the user for the name of the new Gateway instance
read -p "   Enter a name for your new Gateway instance to update >>> " INSTANCE_NAME

execute_docker
# 

echo "✅  Update complete!"
echo