#!/bin/bash
# init

echo
echo
echo "===============  CREATE A NEW GATEWAY INSTANCE ==============="
echo
echo
echo "ℹ️  Press [ENTER] for default values:"
echo

echo
read -p "   Enter Gateway version you want to use [latest/development] (default = \"latest\") >>> " GATEWAY_TAG
if [ "$GATEWAY_TAG" == "" ]
then
  GATEWAY_TAG="latest"
fi

# Ask the user for the name of the new Gateway instance
read -p "   Enter a name for your new Gateway instance (default = \"gateway\") >>> " INSTANCE_NAME
if [ "$INSTANCE_NAME" == "" ]
then
  INSTANCE_NAME="gateway"
  DEFAULT_FOLDER="gateway_files"
else
  DEFAULT_FOLDER="${INSTANCE_NAME}_files"
fi

# Ask the user for the folder location to save files
read -p "   Enter the folder name where your Gateway files will be saved (default = \"$DEFAULT_FOLDER\") >>> " FOLDER
if [ "$FOLDER" == "" ]
then
  FOLDER=$PWD/$DEFAULT_FOLDER
elif [[ ${FOLDER::1} != "/" ]]; then
  FOLDER=$PWD/$FOLDER
fi
CONF_FOLDER="$FOLDER/conf"
LOGS_FOLDER="$FOLDER/logs"
CERTS_FOLDER="$FOLDER/certs"


# Ask the user for the hummingbot certs passphrase
prompt_passphrase () {
echo
read -s -p "   Enter the passphrase you used to generate certificates in Hummingbot  >>> " PASSPHRASE
if [ "$PASSPHRASE" == "" ]
then
 echo
 echo
 echo "‼️  ERROR - passphrase cannot be blank"
 prompt_passphrase
fi
}
prompt_passphrase

# Get GMT offset from local system time
GMT_OFFSET=$(date +%z)

# Check available open port for Gateway
PORT=15888
LIMIT=$((PORT+1000))
while [[ $PORT -le LIMIT ]]
  do
    if [[ $(netstat -nat | grep "$PORT") ]]; then
      # check another port
      ((PORT = PORT + 1))
    else
      break
    fi
done

echo
echo "ℹ️  Confirm below if the instance and its folders are correct:"
echo

printf "%30s %5s\n" "Gateway instance name:" "$INSTANCE_NAME"
printf "%30s %5s\n" "Version:" "hummingbot/gateway:$GATEWAY_TAG"
echo
printf "%30s %5s\n" "Hummingbot instance ID:" "$HUMMINGBOT_INSTANCE_ID"
printf "%30s %5s\n" "Gateway conf path:" "$CONF_FOLDER"
printf "%30s %5s\n" "Gateway log path:" "$LOGS_FOLDER"
printf "%30s %5s\n" "Gateway certs path:" "$CERTS_FOLDER"
printf "%30s %5s\n" "Gateway port:" "$PORT"
echo

prompt_existing_certs_path () {
  echo
  read -p "   Enter the path to the folder where Hummingbot certificates are stored. >>>" CERTS_PATH_TO_COPY
  if  [ "$CERTS_PATH_TO_COPY" == "" ]
  then
    echo
    echo "After installation, set certificatePath in $CONF_FOLDER/server.yml to run Gateway in SSL mode"
  else
    # Check if source folder exists
    if [ ! -d "$CERTS_PATH_TO_COPY" ]; then
      echo "Error: $CERTS_PATH_TO_COPY does not exist or is not a directory"
      exit 1
    fi
    # Copy all files in the source folder to the destination folder
    cp -r $CERTS_PATH_TO_COPY/* $CERTS_FOLDER/
    # Confirm that the files were copied
    if [ $? -eq 0 ]; then
      echo "Files successfully copied from $CERTS_PATH_TO_COPY to $CERTS_FOLDER"
    else
      echo "Error copying files from $CERTS_PATH_TO_COPY to $CERTS_FOLDER"
      exit 1
    fi
  fi
}

prompt_proceed () {
 echo
 read -p "  Do you want to proceed with installation? [Y/N] >>> " PROCEED
 if [ "$PROCEED" == "" ]
 then
 prompt_proceed
 else
  if [[ "$PROCEED" != "Y" && "$PROCEED" != "y" ]]
  then
    PROCEED="N"
  fi
 fi
}

# Execute docker commands
create_instance () {
   echo
   echo "Creating Gateway instance ... "
   echo
   # 1) Create main folder for your new instance
   mkdir $FOLDER
   # 2) Create subfolders for gateway files
   mkdir $CONF_FOLDER
   mkdir $LOGS_FOLDER
   mkdir $CERTS_FOLDER
   # 3) Set required permissions to save gateway password the first time
   sudo chmod a+rw $CONF_FOLDER $CERTS_FOLDER
   prompt_existing_certs_path

   # Launch a new instance of gateway
   docker run \
   --name $INSTANCE_NAME \
   -p $PORT:$PORT \
   -p 8080:8080 \
   -v $CONF_FOLDER:/usr/src/app/conf \
   -v $LOGS_FOLDER:/usr/src/app/logs \
   -v $CERTS_FOLDER:/usr/src/app/certs \
   -e GATEWAY_PASSPHRASE="$PASSWORD" \
   hummingbot/gateway:$GATEWAY_TAG
}
prompt_proceed
if [[ "$PROCEED" == "Y" || "$PROCEED" == "y" ]]
then
 create_instance
else
 echo "   Aborted"
 echo
fi
