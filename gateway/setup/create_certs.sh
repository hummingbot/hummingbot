#!/bin/bash

if ! command -v openssl &> /dev/null
then
    echo "openssl could not be found"
    exit
fi
mkdir -p ../certs
cd ../certs
# create CA private key
openssl genrsa -aes128 -out ca_key.pem 2048
# create CA certificate
openssl req -x509 -new -nodes -key ca_key.pem -sha256 -days 9999 -out ca_cert.pem -subj "/CN=localhost"
# create server private key
openssl genrsa -aes128 -out server_key.pem 
# create CSR
openssl req -new -key server_key.pem -out csr.pem -subj "/CN=localhost"
# create certificate signed by CA
openssl x509 -req -days 9999 -in csr.pem -CA ca_cert.pem -CAkey ca_key.pem -CAcreateserial -out server_cert.pem -sha256
rm csr.pem
# create client private key
openssl genrsa -aes128 -out client_key.pem 
# create CSR
openssl req -new -key client_key.pem -out csr.pem -subj "/CN=localhost"
# create certificate signed by CA
openssl x509 -req -days 9999 -in csr.pem -CA ca_cert.pem -CAkey ca_key.pem -CAcreateserial -out client_cert.pem -sha256
rm csr.pem
