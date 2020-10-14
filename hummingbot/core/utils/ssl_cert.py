import secrets
from os.path import join
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from hummingbot import cert_path

CERT_FILE_PATH = cert_path()
CERT_SUBJECT = [
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'xx'),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'xx'),
    x509.NameAttribute(NameOID.LOCALITY_NAME, 'xx'),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'xx'),
    x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
]
ALT_NAMES = ['localhost']
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

    subject = x509.Name(CERT_SUBJECT)

    # Set alternative DNS
    alt_names = []
    for name in ALT_NAMES:
        alt_names.append(x509.DNSName(name))

    builder = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(subject)
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
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


async def create_self_sign_ca_certs():
    """
    Create self-sign CA Cert
    """
    ca_private_key_filename = 'ca-private-key.pem'
    ca_public_key_filename = 'ca-public-key.pem'
    server_private_key_filename = 'server-private-key.pem'
    server_public_key_filename = 'server-public-key.pem'
    server_csr_filename = 'server-csr.pem'

    password = secrets.token_hex(12)
    server_password = None  # 'serverpassword'

    # Create CA Private & Public Keys for signing
    private_key = generate_private_key(ca_private_key_filename, password)
    generate_public_key(private_key, ca_public_key_filename)

    # Create CSR
    server_private_key = generate_private_key(server_private_key_filename, server_password)
    generate_csr(server_private_key, server_csr_filename)

    # Load CSR
    csr_file = open(join(CERT_FILE_PATH, server_csr_filename), 'rb')
    csr = x509.load_pem_x509_csr(csr_file.read(), default_backend())

    # Load CA public key
    ca_public_key_file = open(join(CERT_FILE_PATH, ca_public_key_filename), 'rb')
    ca_public_key = x509.load_pem_x509_certificate(ca_public_key_file.read(), default_backend())

    # Load CA private key
    ca_private_key_file = open(join(CERT_FILE_PATH, ca_private_key_filename), 'rb')
    ca_private_key = serialization.load_pem_private_key(
        ca_private_key_file.read(),
        password.encode('utf-8'),
        default_backend(),
    )

    # Sign CSR
    sign_csr(csr, ca_public_key, ca_private_key, server_public_key_filename)
