#!/bin/bash
# init

# This will generate the gateway-passphrase.yml with the correct permissions.
# The password should match the one from hummingbot that was used to generate
# the configs.

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
