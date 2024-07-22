import binascii
import importlib
import logging
import shutil
from os import DirEntry, scandir
from os.path import exists, join
from typing import Any, Dict, List, Optional, Union, cast

import yaml

from hummingbot import root_path
from hummingbot.client.config.client_config_map import (
    AnonymizedMetricsDisabledMode,
    AnonymizedMetricsEnabledMode,
    ClientConfigMap,
    ColorConfigMap,
    DBOtherMode,
    DBSqliteMode,
    KillSwitchDisabledMode,
    KillSwitchEnabledMode,
    TelegramDisabledMode,
    TelegramEnabledMode,
)
from hummingbot.client.config.config_crypt import BaseSecretsManager, store_password_verification
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter, save_to_yml
from hummingbot.client.config.security import Security
from hummingbot.client.settings import CLIENT_CONFIG_PATH, CONF_DIR_PATH, STRATEGIES_CONF_DIR_PATH
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map_pydantic import (
    AvellanedaMarketMakingConfigMap,
)
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map_pydantic import (
    CrossExchangeMarketMakingConfigMap,
)

encrypted_conf_prefix = "encrypted_"
encrypted_conf_postfix = ".json"
conf_dir_path = CONF_DIR_PATH
strategies_conf_dir_path = STRATEGIES_CONF_DIR_PATH


def migrate_configs(secrets_manager: BaseSecretsManager) -> List[str]:
    logging.getLogger().info("Starting conf migration.")
    errors = backup_existing_dir()
    if len(errors) == 0:
        errors = migrate_global_config()
        if len(errors) == 0:
            errors.extend(migrate_strategy_confs_paths())
            errors.extend(migrate_connector_confs(secrets_manager))
            store_password_verification(secrets_manager)
            logging.getLogger().info("\nConf migration done.")
    else:
        logging.getLogger().error("\nConf migration failed.")
    return errors


def migrate_non_secure_configs_only() -> List[str]:
    logging.getLogger().info("Starting strategies conf migration.")
    errors = backup_existing_dir()
    if len(errors) == 0:
        errors = migrate_global_config()
        if len(errors) == 0:
            errors.extend(migrate_strategy_confs_paths())
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


def migrate_global_config() -> List[str]:
    logging.getLogger().info("\nMigrating the global config...")
    global_config_path = CONF_DIR_PATH / "conf_global.yml"
    errors = []
    if global_config_path.exists():
        with open(str(global_config_path), "r") as f:
            data = yaml.safe_load(f)
        del data["template_version"]
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        _migrate_global_config_modes(client_config_map, data)
        data.pop("kraken_api_tier", None)
        data.pop("key_file_path", None)
        keys = list(data.keys())
        for key in keys:
            if key in client_config_map.keys():
                _migrate_global_config_field(client_config_map, data, key)
        for key in data:
            logging.getLogger().warning(f"Global ConfigVar {key} was not migrated.")
        errors.extend(client_config_map.validate_model())
        if len(errors) == 0:
            save_to_yml(CLIENT_CONFIG_PATH, client_config_map)
            global_config_path.unlink()
            logging.getLogger().info("\nSuccessfully migrated the global config.")
        else:
            errors = [f"client_config_map - {e}" for e in errors]
            logging.getLogger().error(f"The migration of the global config map failed with errors: {errors}")
    return errors


def _migrate_global_config_modes(client_config_map: ClientConfigAdapter, data: Dict):
    client_config_map: Union[ClientConfigAdapter, ClientConfigMap] = client_config_map  # for IDE autocomplete

    kill_switch_enabled = data.pop("kill_switch_enabled")
    kill_switch_rate = data.pop("kill_switch_rate")
    if kill_switch_enabled:
        client_config_map.kill_switch_mode = KillSwitchEnabledMode(kill_switch_rate=kill_switch_rate)
    else:
        client_config_map.kill_switch_mode = KillSwitchDisabledMode()

    _migrate_global_config_field(
        client_config_map.paper_trade, data, "paper_trade_exchanges"
    )
    _migrate_global_config_field(
        client_config_map.paper_trade, data, "paper_trade_account_balance"
    )

    telegram_enabled = data.pop("telegram_enabled")
    telegram_token = data.pop("telegram_token")
    telegram_chat_id = data.pop("telegram_chat_id")
    if telegram_enabled:
        client_config_map.telegram_mode = TelegramEnabledMode(
            telegram_token=telegram_token,
            telegram_chat_id=telegram_chat_id,
        )
    else:
        client_config_map.telegram_mode = TelegramDisabledMode()

    db_engine = data.pop("db_engine")
    db_host = data.pop("db_host")
    db_port = data.pop("db_port")
    db_username = data.pop("db_username")
    db_password = data.pop("db_password")
    db_name = data.pop("db_name")
    if db_engine == "sqlite":
        client_config_map.db_mode = DBSqliteMode()
    else:
        client_config_map.db_mode = DBOtherMode(
            db_engine=db_engine,
            db_host=db_host,
            db_port=db_port,
            db_username=db_username,
            db_password=db_password,
            db_name=db_name,
        )

    _migrate_global_config_field(
        client_config_map.gateway, data, "gateway_api_port"
    )

    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_host"
    )
    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_port"
    )
    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_username"
    )
    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_password"
    )
    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_ssl"
    )
    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_logger"
    )
    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_notifier"
    )
    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_commands"
    )
    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_events"
    )
    _migrate_global_config_field(
        client_config_map.mqtt_bridge, data, "mqtt_autostart"
    )

    anonymized_metrics_enabled = data.pop("anonymized_metrics_enabled")
    anonymized_metrics_interval_min = data.pop("anonymized_metrics_interval_min")
    if anonymized_metrics_enabled:
        client_config_map.anonymized_metrics_mode = AnonymizedMetricsEnabledMode(
            anonymized_metrics_interval_min=anonymized_metrics_interval_min
        )
    else:
        client_config_map.anonymized_metrics_mode = AnonymizedMetricsDisabledMode()

    _migrate_global_config_field(
        client_config_map.global_token, data, "global_token", "global_token_name"
    )
    _migrate_global_config_field(
        client_config_map.global_token, data, "global_token_symbol"
    )

    _migrate_global_config_field(
        client_config_map.commands_timeout, data, "create_command_timeout"
    )
    _migrate_global_config_field(
        client_config_map.commands_timeout, data, "other_commands_timeout"
    )

    color_map: Union[ClientConfigAdapter, ColorConfigMap] = client_config_map.color
    _migrate_global_config_field(color_map, data, "top-pane", "top_pane")
    _migrate_global_config_field(color_map, data, "bottom-pane", "bottom_pane")
    _migrate_global_config_field(color_map, data, "output-pane", "output_pane")
    _migrate_global_config_field(color_map, data, "input-pane", "input_pane")
    _migrate_global_config_field(color_map, data, "logs-pane", "logs_pane")
    _migrate_global_config_field(color_map, data, "terminal-primary", "terminal_primary")
    _migrate_global_config_field(color_map, data, "primary-label", "primary_label")
    _migrate_global_config_field(color_map, data, "secondary-label", "secondary_label")
    _migrate_global_config_field(color_map, data, "success-label", "success_label")
    _migrate_global_config_field(color_map, data, "warning-label", "warning_label")
    _migrate_global_config_field(color_map, data, "info-label", "info_label")
    _migrate_global_config_field(color_map, data, "error-label", "error_label")

    balance_asset_limit = data.pop("balance_asset_limit")
    if balance_asset_limit is not None:
        exchanges = list(balance_asset_limit.keys())
        for e in exchanges:
            if balance_asset_limit[e] is None:
                balance_asset_limit.pop(e)
            else:
                assets = balance_asset_limit[e].keys()
                for a in assets:
                    if balance_asset_limit[e][a] is None:
                        balance_asset_limit[e].pop(a)
        client_config_map.balance_asset_limit = balance_asset_limit


def _migrate_global_config_field(
    cm: ClientConfigAdapter, global_config_data: Dict[str, Any], attr: str, cm_attr: Optional[str] = None
):
    value = global_config_data.pop(attr)
    cm_attr = cm_attr if cm_attr is not None else attr
    if value is not None:
        cm.setattr_no_validation(cm_attr, value)


def migrate_strategy_confs_paths():
    errors = []
    logging.getLogger().info("\nMigrating strategies...")
    for child in conf_dir_path.iterdir():
        if child.is_file() and child.name.endswith(".yml"):
            with open(str(child), "r") as f:
                conf = yaml.safe_load(f)
            if "strategy" in conf and _has_connector_field(conf):
                new_path = strategies_conf_dir_path / child.name
                child.rename(new_path)
                if conf["strategy"] == "avellaneda_market_making":
                    errors.extend(migrate_amm_confs(conf, new_path))
                elif conf["strategy"] == "cross_exchange_market_making":
                    errors.extend(migrate_xemm_confs(conf, new_path))
                logging.getLogger().info(f"Migrated conf for {conf['strategy']}")
    return errors


def migrate_amm_confs(conf, new_path) -> List[str]:
    execution_timeframe = conf.pop("execution_timeframe")
    if execution_timeframe == "infinite":
        conf["execution_timeframe_mode"] = {}
        conf.pop("start_time")
        conf.pop("end_time")
    elif execution_timeframe == "from_date_to_date":
        conf["execution_timeframe_mode"] = {
            "start_datetime": conf.pop("start_time"),
            "end_datetime": conf.pop("end_time"),
        }
    else:
        assert execution_timeframe == "daily_between_times"
        conf["execution_timeframe_mode"] = {
            "start_time": conf.pop("start_time"),
            "end_time": conf.pop("end_time"),
        }
    order_levels = int(conf.pop("order_levels"))
    if order_levels == 1:
        conf["order_levels_mode"] = {}
        conf.pop("level_distances")
    else:
        conf["order_levels_mode"] = {
            "order_levels": order_levels,
            "level_distances": conf.pop("level_distances")
        }
    hanging_orders_enabled = conf.pop("hanging_orders_enabled")
    if not hanging_orders_enabled:
        conf["hanging_orders_mode"] = {}
        conf.pop("hanging_orders_cancel_pct")
    else:
        conf["hanging_orders_mode"] = {
            "hanging_orders_cancel_pct": conf.pop("hanging_orders_cancel_pct")
        }
    if "template_version" in conf:
        conf.pop("template_version")
    try:
        config_map = ClientConfigAdapter(AvellanedaMarketMakingConfigMap(**conf))
        save_to_yml(new_path, config_map)
        errors = []
    except Exception as e:
        logging.getLogger().error(str(e))
        errors = [str(e)]
    return errors


def migrate_xemm_confs(conf, new_path) -> List[str]:
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
        save_to_yml(new_path, config_map)
        errors = []
    except Exception as e:
        logging.getLogger().error(str(e))
        errors = [str(e)]
    return errors


def _has_connector_field(conf: Dict) -> bool:
    return (
        "exchange" in conf
        or "connector_1" in conf  # amm arb
        or "primary_market" in conf  # arbitrage
        or "secondary_exchange" in conf  # celo arb
        or "maker_market" in conf  # XEMM
        or "market" in conf  # dev simple trade
        or "maker_exchange" in conf  # hedge
        or "spot_connector" in conf  # spot-perp arb
        or "connector" in conf  # twap
    )


def migrate_connector_confs(secrets_manager: BaseSecretsManager):
    logging.getLogger().info("\nMigrating connector secure keys...")
    errors = []
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
                suffix = "data_types" if connector_dir.name == "celo" else "utils"
                util_module_path: str = (
                    f"hummingbot.connector.{type_dir.name}.{connector_dir.name}.{connector_dir.name}_{suffix}"
                )
                util_module = importlib.import_module(util_module_path)
                config_keys = getattr(util_module, "KEYS", None)
                if config_keys is not None:
                    errors.extend(_maybe_migrate_encrypted_confs(config_keys))
                other_domains = getattr(util_module, "OTHER_DOMAINS", [])
                for domain in other_domains:
                    config_keys = getattr(util_module, "OTHER_DOMAINS_KEYS")[domain]
                    if config_keys is not None:
                        errors.extend(_maybe_migrate_encrypted_confs(config_keys))
            except ModuleNotFoundError:
                continue
    return errors


def _maybe_migrate_encrypted_confs(config_keys: BaseConnectorConfigMap) -> List[str]:
    cm = ClientConfigAdapter(config_keys)
    found_one = False
    files_to_remove = []
    missing_fields = []
    for el in cm.traverse():
        if el.client_field_data is not None:
            key_path = conf_dir_path / f"{encrypted_conf_prefix}{el.attr}{encrypted_conf_postfix}"
            if key_path.exists():
                with open(key_path, 'r') as f:
                    json_str = f.read()
                value = binascii.hexlify(json_str.encode()).decode()
                if not el.client_field_data.is_secure:
                    value = Security.secrets_manager.decrypt_secret_value(el.attr, value)
                cm.setattr_no_validation(el.attr, value)
                files_to_remove.append(key_path)
                found_one = True
            else:
                missing_fields.append(el.attr)
    errors = []
    if found_one:
        if len(missing_fields) != 0:
            errors = [f"{config_keys.connector} - missing fields: {missing_fields}"]
        if len(errors) == 0:
            errors = cm.validate_model()
        if errors:
            errors = [f"{config_keys.connector} - {e}" for e in errors]
            logging.getLogger().error(f"The migration of {config_keys.connector} failed with errors: {errors}")
        else:
            Security.update_secure_config(cm)
            logging.getLogger().info(f"Migrated secure keys for {config_keys.connector}")
        for f in files_to_remove:
            f.unlink()
    return errors
