from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel


class SSLConfigMap(BaseClientModel):
    caCertificatePath: str = Field(default="/usr/src/app/certs/ca_cert.pem")
    certificatePath: str = Field(default="/usr/src/app/certs/server_cert.pem")
    keyPath: str = Field(default="/usr/src/app/certs/server_key.pem")
