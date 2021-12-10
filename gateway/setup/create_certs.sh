if ! command -v openssl &> /dev/null
then
    echo "openssl could not be found"
    exit
fi
mkdir -p ../certs
cd ../certs
openssl genrsa -des3 -out server_key.pem
openssl req -new -key server_key.pem -out csr.pem -subj "/C=/ST=/L=/O=/CN=localhost"
openssl x509 -req -days 9999 -in csr.pem -signkey key.pem -out server_cert.pem
rm csr.pem
