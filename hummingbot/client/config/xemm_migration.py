import logging
import shutil
from typing import List

import yaml

from hummingbot.client.config.config_helpers import ClientConfigAdapter, save_to_yml
from hummingbot.client.settings import CONF_DIR_PATH
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map_pydantic import (
    CrossExchangeMarketMakingConfigMap,
)

conf_dir_path = CONF_DIR_PATH


def migrate_xemm() -> List[str]:
    logging.getLogger().info("Starting conf migration.")
    errors = backup_existing_dir()
    if len(errors) == 0:
        errors.extend(migrate_xemm_confs())
        logging.getLogger().info("\nConf migration done.")
    else:
        logging.getLogger().error("\nConf migration failed.")
    return errors


def backup_existing_dir() -> List[str]:
    errors = []
    if conf_dir_path.exists():
        backup_path = conf_dir_path.parent / "conf_backup"
        if backup_path.exists():
            errors = [
                (
                    f"\nBackup path {backup_path} already exists."
                    f"\nThe migration script cannot backup you existing"
                    f"\nconf files without overwriting that directory."
                    f"\nPlease remove it and run the script again."
                )
            ]
        else:
            shutil.copytree(conf_dir_path, backup_path)
            logging.getLogger().info(f"\nCreated a backup of your existing conf directory to {backup_path}")
    return errors


def migrate_xemm_confs():
    errors = []
    logging.getLogger().info("\nMigrating strategies...")
    for child in conf_dir_path.iterdir():
        if child.is_file() and child.name.endswith(".yml"):
            with open(str(child), "r") as f:
                conf = yaml.safe_load(f)
            if "strategy" in conf:
                if conf["strategy"] == "cross_exchange_market_making":
                    if "active_order_canceling" in conf:
                        if conf["active_order_canceling"]:
                            conf["order_refresh_mode"] = {}
                        else:
                            conf["order_refresh_mode"] = {
                                "cancel_order_threshold": conf["cancel_order_threshold"],
                                "limit_order_min_expiration": conf["limit_order_min_expiration"]
                            }
                        conf.pop("active_order_canceling")
                        conf.pop("cancel_order_threshold")
                        conf.pop("limit_order_min_expiration")

                    if "use_oracle_conversion_rate" in conf:
                        if conf["use_oracle_conversion_rate"]:
                            conf["conversion_rate_mode"] = {}
                        else:
                            conf["conversion_rate_mode"] = {
                                "taker_to_maker_base_conversion_rate": conf["taker_to_maker_base_conversion_rate"],
                                "taker_to_maker_quote_conversion_rate": conf["taker_to_maker_quote_conversion_rate"]
                            }
                        conf.pop("use_oracle_conversion_rate")
                        conf.pop("taker_to_maker_base_conversion_rate")
                        conf.pop("taker_to_maker_quote_conversion_rate")

                    if "template_version" in conf:
                        conf.pop("template_version")

                    try:
                        config_map = ClientConfigAdapter(CrossExchangeMarketMakingConfigMap(**conf))

                        save_to_yml(child.absolute(), config_map)

                        logging.getLogger().info(f"Migrated conf for {conf['strategy']}")
                    except Exception as e:
                        errors.extend((str(e)))
    return errors
