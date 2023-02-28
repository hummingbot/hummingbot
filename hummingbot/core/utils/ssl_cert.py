"""
Functions for generating keys and certificates
"""
from datetime import datetime, timedelta
from os import listdir
from os.path import join
from typing import TYPE_CHECKING

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from hummingbot import root_path
from hummingbot.core.gateway import get_gateway_paths

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

CERT_SUBJECT = [
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'localhost'),
    x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
]
# Set alternative DNS
SAN_DNS = [x509.DNSName('localhost')]
VALIDITY_DURATION = 365
CONF_DIR_PATH = root_path() / "conf"


def generate_private_key(password, filepath):
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
    # filepath = join(CERT_FILE_PATH, filename)
    with open(filepath, "wb") as key_file:
        key_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=algorithm,
            )
        )

    return private_key


def generate_public_key(private_key, filepath):
    """
    Generate Public Key
    """

    # Subject info for certification
    subject = x509.Name(CERT_SUBJECT)

    # Use subject as issuer on self-sign certificate
    cert_issuer = subject

    # Set certification validity duration
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
    # filepath = join(CERT_FILE_PATH, filename)
    with open(filepath, "wb") as cert_file:
        cert_file.write(public_key.public_bytes(serialization.Encoding.PEM))

    return public_key


def generate_csr(private_key, filepath):
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

    # filepath = join(CERT_FILE_PATH, filename)
    with open(filepath, "wb") as csr_file:
        csr_file.write(csr.public_bytes(serialization.Encoding.PEM))

    return csr


def sign_csr(csr, ca_public_key, ca_private_key, filepath):
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

        # filepath = join(CERT_FILE_PATH, filename)
        with open(filepath, "wb") as key_file:
            key_file.write(public_key.public_bytes(serialization.Encoding.PEM))

        return filepath
    except Exception as e:
        raise Exception(e.output)


ca_key_filename = 'ca_key.pem'
ca_cert_filename = 'ca_cert.pem'
server_key_filename = 'server_key.pem'
server_cert_filename = 'server_cert.pem'
server_csr_filename = 'server_csr.pem'
client_key_filename = 'client_key.pem'
client_cert_filename = 'client_cert.pem'
client_csr_filename = 'client_csr.pem'


def certs_files_exist(client_config_map: "ClientConfigAdapter") -> bool:
    """
    Check if the necessary key and certificate files exist
    """
    required_certs = [ca_key_filename, ca_cert_filename,
                      server_key_filename, server_cert_filename,
                      client_key_filename, client_cert_filename]

    file_list = listdir(get_gateway_paths(client_config_map).local_certs_path.as_posix())
    return all(elem in file_list for elem in required_certs)


def create_self_sign_certs(pass_phase: str, cert_path: str):
    """
    Create self-sign CA Cert
    """

    filepath_list = {
        'ca_key': join(cert_path, ca_key_filename),
        'ca_cert': join(cert_path, ca_cert_filename),
        'server_key': join(cert_path, server_key_filename),
        'server_cert': join(cert_path, server_cert_filename),
        'server_csr': join(cert_path, server_csr_filename),
        'client_key': join(cert_path, client_key_filename),
        'client_cert': join(cert_path, client_cert_filename),
        'client_csr': join(cert_path, client_csr_filename)
    }

    # Create CA Private & Public Keys for signing
    ca_private_key = generate_private_key(pass_phase, filepath_list['ca_key'])
    generate_public_key(ca_private_key, filepath_list['ca_cert'])

    # Create Server Private & Public Keys for signing
    server_private_key = generate_private_key(pass_phase, filepath_list['server_key'])
    # Create CSR
    generate_csr(server_private_key, filepath_list['server_csr'])
    # Load CSR
    with open(filepath_list['server_csr'], 'rb') as server_csr_file:
        server_csr = x509.load_pem_x509_csr(server_csr_file.read(), default_backend())

    # Create Client CSR
    # local certificate must be unencrypted. Currently, Requests does not support using encrypted keys.
    client_private_key = generate_private_key(None, filepath_list['client_key'])
    # Create CSR
    generate_csr(client_private_key, filepath_list['client_csr'])
    # Load CSR
    with open(filepath_list['client_csr'], 'rb') as client_csr_file:
        client_csr = x509.load_pem_x509_csr(client_csr_file.read(), default_backend())

    # Load CA public key
    with open(filepath_list['ca_cert'], 'rb') as ca_cert_file:
        ca_cert = x509.load_pem_x509_certificate(ca_cert_file.read(), default_backend())
    # Load CA private key
    with open(filepath_list['ca_key'], 'rb') as ca_key_file:
        ca_key = serialization.load_pem_private_key(
            ca_key_file.read(),
            pass_phase.encode('utf-8'),
            default_backend(),
        )

    # Sign Server Cert with CSR
    sign_csr(server_csr, ca_cert, ca_key, filepath_list['server_cert'])
    # Sign Client Cert with CSR
    sign_csr(client_csr, ca_cert, ca_key, filepath_list['client_cert'])
