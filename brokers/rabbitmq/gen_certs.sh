#!/usr/bin/env bash

LIFETIME_DAYS=120

if [[ ! -d certs ]]; then
    mkdir certs
fi
cd certs/
echo "Generating CA private key..."
openssl genrsa -out RMQ-CA-Key.pem
echo "Signing CA private key..."
openssl req -new -key RMQ-CA-Key.pem -x509 -days ${LIFETIME_DAYS} -out RMQ-CA-cert.pem
echo "Generating Server private key..."
openssl genrsa -out RMQ-server-key.pem
echo "Generate a CSR (Certificate Signing Request)..."
# openssl req -new -config openssl.cnf -key RMQ-server_key.pem -out RMQ-signingrequest.csr
openssl req -new -key RMQ-server-key.pem -out RMQ-signingrequest.csr
echo "Generate the self-signed certificate using signing.csr, CA-Key.pem, and CA-cert.pem..."
openssl x509 -req -days ${LIFETIME_DAYS} -in RMQ-signingrequest.csr -CA RMQ-CA-cert.pem -CAkey RMQ-CA-Key.pem -CAcreateserial -out RMQ-server-cert.pem
echo "Concatenate both private and public certificates to create a .pem file..."
cd -


echo "Follow the below configuration for your RabbitMQ instance:"
echo "----------------------------------------------------------"
echo "
listeners.ssl.default = 5671
ssl_options.cacertfile = <RMQ-CA-cert.pem>
ssl_options.certfile = <RMQ-server-cert.pem>
ssl_options.keyfile = <RMQ-server-key.pem>
ssl_options.verify = verify_peer
ssl_options.fail_if_no_peer_cert = true
"
echo "----------------------------------------------------------"
