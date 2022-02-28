#!/bin/bash

showHelp() {
cat << EOF  
Usage: ./update_ssl_conf.sh [-h] [-f ...] [-c ...] [-e ...] [-k ...]
Update the specified configuration in the specified ssl.yml file

-h      Display help.

-f      Directory containing the ssl.yml.

-c      Intended value for the caCertificatePath configuration.

-e      Intended value for the certificatePath configuration.

-k      Intended value for the keyPath configuration.

EOF
}

CERT_FOLDER="$(pwd -P)/../certs"
CA_CERT_PATH="/usr/src/app/certs/ca_cert.pem"
CERT_PATH="/usr/src/app/certs/server_cert.pem"
KEY_PATH="/usr/src/app/certs/server_key.pem"


while getopts ":f:c:e:k:h" options; do
    case "${options}" in
        f) 
            CERT_FOLDER="${OPTARG}"
            ;;
        c)
            CA_CERT_PATH="${OPTARG}"
            ;;
        e)
            CERT_PATH="${OPTARG}"
            ;;
        k)
            KEY_PATH="${OPTARG}"
            ;;
        h)
            showHelp
            exit 0
            ;;
        :)
            echo "Error: -${OPTARG} requires an argument."
            showHelp
            exit 1
            ;;
        *)
            showHelp
            exit 1
    esac
done

echo CERT_FOLDER="$CERT_FOLDER"
echo CA_CERT_PATH="$CA_CERT_PATH"
echo CERT_PATH="$CERT_PATH"
echo KEY_PATH="$KEY_PATH"

if [[ ! -d "$CERT_FOLDER" ]]; then
    echo "CERT_FOLDER: $CERT_FOLDER folder does not exist"
    exit 1
fi

if [[ ! -f "$CA_CERT_PATH" ]]; then
    echo "CA_CERT_PATH: $CA_CERT_PATH file does not exist"
    exit 1
fi

if [[ ! -f "$CERT_PATH" ]]; then
    echo "CERT_PATH: $CERT_PATH file does not exist"
    exit 1
fi

if [[ ! -f "$KEY_PATH" ]]; then
    echo "KEY_PATH: $KEY_PATH file does not exist"
    exit 1
fi

cp "$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/../src/templates/ssl.yml" "$CERT_FOLDER/ssl.yml"
sed -i'.bak' -e "/caCertificatePath:/ s#[^ ][^ ]*\$#$CA_CERT_PATH#" "$CERT_FOLDER/ssl.yml"
sed -i'.bak' -e "/certificatePath:/ s#[^ ][^ ]*\$#$CERT_PATH#" "$CERT_FOLDER/ssl.yml"
sed -i'.bak' -e "/keyPath:/ s#[^ ][^ ]*\$#$KEY_PATH#" "$CERT_FOLDER/ssl.yml"

echo "updated $CERT_FOLDER/ssl.yml"