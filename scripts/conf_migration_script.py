import argparse
import binascii
import importlib
import shutil
from os import DirEntry, scandir
from os.path import exists, join
from typing import List, cast

import yaml

from hummingbot import root_path
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.security import Security
from hummingbot.client.settings import CONF_DIR_PATH, STRATEGIES_CONF_DIR_PATH

encrypted_conf_prefix = "encrypted_"
encrypted_conf_postfix = ".json"
conf_dir_path = CONF_DIR_PATH
strategies_conf_dir_path = STRATEGIES_CONF_DIR_PATH


def migrate(password: str):
    print("Starting conf migration.")
    backup_existing_dir()
    migrate_strategy_confs()
    migrate_connector_confs(password)


def backup_existing_dir():
    if conf_dir_path.exists():
        backup_path = conf_dir_path.parent / "conf_backup"
        if backup_path.exists():
            raise RuntimeError(
                f"\nBackup path {backup_path} already exists. The migration script cannot backup you"
                f" exiting conf files without overwriting that directory. Please remove it and"
                f" run the script again."
            )
        shutil.copytree(conf_dir_path, backup_path)
        print(f"\nCreated a backup of your existing conf directory to {backup_path}")


def migrate_strategy_confs():
    print("\nMigrating strategies...")
    for child in conf_dir_path.iterdir():
        if child.is_file() and child.name.endswith(".yml"):
            with open(str(child), "r") as f:
                conf = yaml.safe_load(f)
            if "strategy" in conf and "exchange" in conf:
                new_path = strategies_conf_dir_path / child.name
                child.rename(new_path)
                print(f"Migrated conf for {conf['strategy']}")


def migrate_connector_confs(password: str):
    print("\nMigrating connector secure keys...")
    secrets_manager = ETHKeyFileSecretManger(password)
    Security.secrets_manager = secrets_manager
    connector_exceptions = ["paper_trade"]
    type_dirs: List[DirEntry] = [
        cast(DirEntry, f) for f in
        scandir(f"{root_path() / 'hummingbot' / 'connector'}")
        if f.is_dir()
    ]
    for type_dir in type_dirs:
        connector_dirs: List[DirEntry] = [
            cast(DirEntry, f) for f in scandir(type_dir.path)
            if f.is_dir() and exists(join(f.path, "__init__.py"))
        ]
        for connector_dir in connector_dirs:
            if connector_dir.name.startswith("_") or connector_dir.name in connector_exceptions:
                continue
            try:
                util_module_path: str = (
                    f"hummingbot.connector.{type_dir.name}.{connector_dir.name}.{connector_dir.name}_utils"
                )
                util_module = importlib.import_module(util_module_path)
                config_keys = getattr(util_module, "KEYS", None)
                if config_keys is not None:
                    _maybe_migrate_encrypted_confs(config_keys)
                other_domains = getattr(util_module, "OTHER_DOMAINS", [])
                for domain in other_domains:
                    config_keys = getattr(util_module, "OTHER_DOMAINS_KEYS")[domain]
                    if config_keys is not None:
                        _maybe_migrate_encrypted_confs(config_keys)
            except ModuleNotFoundError:
                continue


def _maybe_migrate_encrypted_confs(config_keys: BaseConnectorConfigMap):
    cm = ClientConfigAdapter(config_keys)
    found_one = False
    files_to_remove = []
    missing_fields = []
    for el in cm.traverse():
        if el.client_field_data is not None and el.client_field_data.is_secure:
            key_path = conf_dir_path / f"{encrypted_conf_prefix}{el.attr}{encrypted_conf_postfix}"
            if key_path.exists():
                with open(key_path, 'r') as f:
                    json_str = f.read()
                encrypted = binascii.hexlify(json_str.encode()).decode()
                cm.setattr_no_validation(el.attr, encrypted)
                files_to_remove.append(key_path)
                found_one = True
            else:
                missing_fields.append(el.attr)
    if found_one:
        if len(missing_fields) != 0:
            raise RuntimeError(
                f"The migration of {config_keys.connector} failed because of missing fields: {missing_fields}"
            )
        errors = cm.validate_model()
        if errors:
            raise RuntimeError(f"The migration of {config_keys.connector} failed with errors: {errors}")
        Security.update_secure_config(cm.connector, cm)
        for f in files_to_remove:
            f.unlink()
        print(f"Migrated secure keys for {config_keys.connector}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate the HummingBot confs")
    parser.add_argument("password", type=str, help="Required to migrate all encrypted configs.")
    args = parser.parse_args()
    migrate(args.password)
    print("\nConf migration done.")
