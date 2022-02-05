#!/bin/bash
# init

echo
echo
echo "===============  UPDATE GATEWAY CONFIGURATION FILE(S) ==============="
echo
echo

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
sed -i '/ENABLE_TELEMETRY: .*/d;/^ *$/d' $CONFIGURATION_FILE
echo "ENABLE_TELEMETRY: $TELEMETRY"  >> $CONFIGURATION_FILE
echo "" >> $CONFIGURATION_FILE
