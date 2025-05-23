import os
from pathlib import Path

# Global constants
CONF_DIR_PATH = Path(os.getenv("CONF_PATH", "conf"))
CONF_PREFIX = "conf_"
CONF_POSTFIX = "_strategy"

DEFAULT_LOG_FILE_PATH = "logs"
DEFAULT_GATEWAY_CERTS_PATH = "certs"
PASSWORD_VERIFICATION_PATH = "hummingbot_password.yml"
