#!/bin/bash
# init

echo
echo
echo "===============  UPDATE GATEWAY CONFIGURATION FILE(S) ==============="
echo
echo

prompt_gateway_passphrase () {
read -p "Enter Gateway certificate passphrase >>> " GATEWAY_PASSPHRASE
if [ "$GATEWAY_PASSPHRASE" == "" ]
then
  echo "No value entered, enter passphrase used to generate certificate."
  prompt_gateway_passphrase
fi
}

update_passphrase_file() {
prompt_gateway_passphrase
PASSPHRASE_FILE="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../conf/gateway-passphrase.yml"
echo "  Updating Gateway passphrase file with passphrase and correct permission."
echo "" > $PASSPHRASE_FILE # clear existing file data
echo "CERT_PASSPHRASE: '$GATEWAY_PASSPHRASE'" >> $PASSPHRASE_FILE
echo "" >> $PASSPHRASE_FILE

sudo chmod 0600 $PASSPHRASE_FILE  # set mod
}
update_passphrase_file

prompt_to_allow_telemetry () {
read -p "Do you want to enable telemetry?  [yes/no] (default = \"no\")>>> " TELEMETRY
if [[ "$TELEMETRY" == "" || "$TELEMETRY" == "No" || "$TELEMETRY" == "no" ]]
then
  echo "Telemetry disabled."
  TELEMETRY=false
elif [[ "$TELEMETRY" == "Yes" || "$TELEMETRY" == "yes" ]]
then
  echo "Telemetry enabled."
  TELEMETRY=true
else
  echo "Invalid input, try again."
  prompt_to_allow_telemetry
fi
}
prompt_to_allow_telemetry

# update config file
CONFIGURATION_FILE="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../conf/gateway-config.yml"
echo "ENABLE_TELEMETRY: '$TELEMETRY'"  >> $CONFIGURATION_FILE
echo "" >> $CONFIGURATION_FILE
