import os
import platform
from pathlib import Path


def get_system():
    return platform.system()


def get_installation_type():
    if os.environ.get("INSTALLATION_TYPE", "").lower() == "docker":
        return "docker"
    package_dir = Path(__file__).resolve().parent.parent.parent
    bin_dir = [f for f in os.scandir(str(package_dir)) if f.name == "bin" and f.is_dir()]
    if not bin_dir:
        return "binary"
    return "source"


client_system = get_system()
installation_type = get_installation_type()
