from os import listdir
from os.path import join
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from hummingbot import cert_path
from distutils.util import strtobool

CERT_FILE_PATH = cert_path()
CERT_SUBJECT = [
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'localhost'),
    x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
]
# Set alternative DNS
SAN_DNS = [x509.DNSName('localhost')]
VALIDITY_DURATION = 365


def generate_private_key(filename, password):
    """
    Generate Private Key
    """

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    algorithm = serialization.NoEncryption()
    if password:
        algorithm = serialization.BestAvailableEncryption(password.encode("utf-8"))

    # Write key to cert
    filepath = join(CERT_FILE_PATH, filename)
    with open(filepath, "wb") as key_file:
        key_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=algorithm,
            )
        )

    return private_key


def generate_public_key(private_key, filename):
    """
    Generate Public Key
    """

    # Subject info for certification
    subject = x509.Name(CERT_SUBJECT)

    # Use subject as issuer on self-sign certificate
    cert_issuer = subject

    # Set certifacation validity duration
    current_datetime = datetime.utcnow()
    expiration_datetime = current_datetime + timedelta(days=VALIDITY_DURATION)

    # Create certification
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(cert_issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(current_datetime)
        .not_valid_after(expiration_datetime)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    )

    # Use private key to sign cert
    public_key = builder.sign(
        private_key,
        hashes.SHA256(),
        default_backend()
    )

    # Write key to cert
    filepath = join(CERT_FILE_PATH, filename)
    with open(filepath, "wb") as cert_file:
        cert_file.write(public_key.public_bytes(serialization.Encoding.PEM))

    return public_key


def generate_csr(private_key, filename):
    """
    Generate CSR (Certificate Signing Request)
    """

    # CSR subject cannot be the same as CERT_SUBJECT
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
    ])

    builder = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .add_extension(x509.SubjectAlternativeName(SAN_DNS), critical=False)
    )

    csr = builder.sign(private_key, hashes.SHA256(), default_backend())

    filepath = join(CERT_FILE_PATH, filename)
    with open(filepath, "wb") as csr_file:
        csr_file.write(csr.public_bytes(serialization.Encoding.PEM))

    return csr


def sign_csr(csr, ca_public_key, ca_private_key, filename):
    """
    Sign CSR with CA public & private keys & generate a verified public key
    """

    current_datetime = datetime.utcnow()
    expiration_datetime = current_datetime + timedelta(days=VALIDITY_DURATION)

    try:
        builder = (
            x509.CertificateBuilder()
            .subject_name(csr.subject)
            .issuer_name(ca_public_key.subject)
            .public_key(csr.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(current_datetime)
            .not_valid_after(expiration_datetime)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True,)
        )

        for extension in csr.extensions:
            builder = builder.add_extension(extension.value, extension.critical)

        public_key = builder.sign(
            private_key=ca_private_key,
            algorithm=hashes.SHA256(),
            backend=default_backend(),
        )

        filepath = join(CERT_FILE_PATH, filename)
        with open(filepath, "wb") as key_file:
            key_file.write(public_key.public_bytes(serialization.Encoding.PEM))

        return filepath
    except Exception as e:
        raise Exception(e.output)


def create_self_sign_certs(enabled = 'no'):
    """
    Create self-sign CA Cert
    """
    ca_key_filename = 'ca_key.pem'
    ca_cert_filename = 'ca_cert.pem'
    server_key_filename = 'server_key.pem'
    server_cert_filename = 'server_cert.pem'
    server_csr_filename = 'server_csr.pem'
    client_key_filename = 'client_key.pem'
    client_cert_filename = 'client_cert.pem'
    client_csr_filename = 'client_csr.pem'

    # certs required for gateway
    required_certs = [ca_key_filename, ca_cert_filename,
                      server_key_filename, server_cert_filename,
                      client_key_filename, client_cert_filename]

    filelist = listdir(CERT_FILE_PATH)
    contain_required_certs = all(elem in filelist for elem in required_certs)

    if strtobool(enabled) and not contain_required_certs:

        # import only after global config has already been loaded to retrieve client_id
        from hummingbot.client.config.global_config_map import global_config_map

        password = global_config_map["gateway_cert_passphrase"].value
        # local certificate must be unencrypted. Currently, Requests does not support using encrypted keys.
        client_password = None

        if not password:
            print("Error: Please set gateway_cert_passphrase and retry\nCert passphrase is required for Gateway SSL")
            return

        # Create CA Private & Public Keys for signing
        ca_private_key = generate_private_key(ca_key_filename, password)
        generate_public_key(ca_private_key, ca_cert_filename)

        # Create Server Private & Public Keys for signing
        server_private_key = generate_private_key(server_key_filename, password)
        # Create CSR
        generate_csr(server_private_key, server_csr_filename)
        # Load CSR
        server_csr_file = open(join(CERT_FILE_PATH, server_csr_filename), 'rb')
        server_csr = x509.load_pem_x509_csr(server_csr_file.read(), default_backend())

        # Create Client CSR
        client_private_key = generate_private_key(client_key_filename, client_password)
        # Create CSR
        generate_csr(client_private_key, client_csr_filename)
        # Load CSR
        client_csr_file = open(join(CERT_FILE_PATH, client_csr_filename), 'rb')
        client_csr = x509.load_pem_x509_csr(client_csr_file.read(), default_backend())

        # Load CA public key
        ca_cert_file = open(join(CERT_FILE_PATH, ca_cert_filename), 'rb')
        ca_cert = x509.load_pem_x509_certificate(ca_cert_file.read(), default_backend())
        # Load CA private key
        ca_key_file = open(join(CERT_FILE_PATH, ca_key_filename), 'rb')
        ca_key = serialization.load_pem_private_key(
            ca_key_file.read(),
            password.encode('utf-8'),
            default_backend(),
        )

        try:
            # Sign Server Cert with CSR
            sign_csr(server_csr, ca_cert, ca_key, server_cert_filename)
            # Sign Client Cert with CSR
            sign_csr(client_csr, ca_cert, ca_key, client_cert_filename)

        except Exception as e:
            raise Exception(e.output)
    else:
        # TODO: condition for future certs re-generate, removal, etc ops
        pass
