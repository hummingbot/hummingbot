import contextlib
import inspect
import json
import logging
import shutil
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, time, datetime
from decimal import Decimal
from os import listdir, unlink
from os.path import isfile, join
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Union,
)

import ruamel.yaml
import yaml
from eth_account import Account
from pydantic import ValidationError
from pydantic.fields import FieldInfo
from pydantic.main import ModelMetaclass, validate_model
from yaml import SafeDumper

from hummingbot import get_strategy_list, root_path
from hummingbot.client.config.config_data_types import (
    BaseClientModel, ClientConfigEnum, ClientFieldData
)
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.security import Security
from hummingbot.client.settings import (
    AllConnectorSettings,
    CONF_FILE_PATH,
    CONF_POSTFIX,
    CONF_PREFIX,
    GLOBAL_CONFIG_PATH,
    TEMPLATE_PATH,
    TRADE_FEES_CONFIG_PATH,
)

# Use ruamel.yaml to preserve order and comments in .yml file
yaml_parser = ruamel.yaml.YAML()  # legacy


def decimal_representer(dumper: SafeDumper, data: Decimal):
    return dumper.represent_float(float(data))


def enum_representer(dumper: SafeDumper, data: ClientConfigEnum):
    return dumper.represent_str(str(data))


def date_representer(dumper: SafeDumper, data: date):
    return dumper.represent_date(data)


def time_representer(dumper: SafeDumper, data: time):
    return dumper.represent_str(data.strftime("%H:%M:%S"))


def datetime_representer(dumper: SafeDumper, data: datetime):
    return dumper.represent_datetime(data)


yaml.add_representer(
    data_type=Decimal, representer=decimal_representer, Dumper=SafeDumper
)
yaml.add_multi_representer(
    data_type=ClientConfigEnum, multi_representer=enum_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=date, representer=date_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=time, representer=time_representer, Dumper=SafeDumper
)
yaml.add_representer(
    data_type=datetime, representer=datetime_representer, Dumper=SafeDumper
)


class ConfigValidationError(Exception):
    pass


@dataclass()
class ConfigTraversalItem:
    depth: int
    config_path: str
    attr: str
    value: Any
    printable_value: str
    client_field_data: Optional[ClientFieldData]
    field_info: FieldInfo


class ClientConfigAdapter:
    def __init__(self, hb_config: BaseClientModel):
        self._hb_config = hb_config

    def __getattr__(self, item):
        if item == "_hb_config":
            value = super().__getattribute__(item)
        else:
            value = getattr(self._hb_config, item)
            if isinstance(value, BaseClientModel):
                value = ClientConfigAdapter(value)
        return value

    def __setattr__(self, key, value):
        if key == "_hb_config":
            super().__setattr__(key, value)
        else:
            try:
                self._hb_config.__setattr__(key, value)
            except ValidationError as e:
                raise ConfigValidationError(retrieve_validation_error_msg(e))

    def __repr__(self):
        return f"{self.__class__.__name__}.{self._hb_config.__repr__()}"

    def __eq__(self, other):
        if isinstance(other, ClientConfigAdapter):
            eq = self._hb_config.__eq__(other._hb_config)
        else:
            eq = super().__eq__(other)
        return eq

    @property
    def hb_config(self) -> BaseClientModel:
        return self._hb_config

    @property
    def title(self) -> str:
        return self._hb_config.Config.title

    def is_required(self, attr: str) -> bool:
        return self._hb_config.is_required(attr)

    def keys(self) -> Generator[str, None, None]:
        return self._hb_config.__fields__.keys()

    def setattr_no_validation(self, attr: str, value: Any):
        with self._disable_validation():
            setattr(self, attr, value)

    def traverse(self) -> Generator[ConfigTraversalItem, None, None]:
        """The intended use for this function is to simplify config map traversals in the client code.

        If the field is missing, its value will be set to `None` and its printable value will be set to
        'MISSING_AND_REQUIRED'.
        """
        depth = 0
        for attr, field in self._hb_config.__fields__.items():
            if hasattr(self, attr):
                value = getattr(self, attr)
                printable_value = (
                    str(value) if not isinstance(value, ClientConfigAdapter) else value.hb_config.Config.title
                )
                field_info = field.field_info
                client_field_data = field_info.extra.get("client_data")
            else:
                value = None
                printable_value = "&cMISSING_AND_REQUIRED"
                client_field_data = self.get_client_data(attr)
                field_info = self._hb_config.__fields__[attr].field_info
            yield ConfigTraversalItem(
                depth, attr, attr, value, printable_value, client_field_data, field_info
            )
            if isinstance(value, ClientConfigAdapter):
                for traversal_item in value.traverse():
                    traversal_item.depth += 1
                    config_path = f"{attr}.{traversal_item.config_path}"
                    traversal_item.config_path = config_path
                    yield traversal_item

    async def get_client_prompt(self, attr_name: str) -> Optional[str]:
        prompt = None
        client_data = self.get_client_data(attr_name)
        if client_data is not None:
            prompt_fn = client_data.prompt
            if inspect.iscoroutinefunction(prompt_fn):
                prompt = await prompt_fn(self._hb_config)
            else:
                prompt = prompt_fn(self._hb_config)
        return prompt

    def is_secure(self, attr_name: str) -> bool:
        client_data = self.get_client_data(attr_name)
        secure = client_data is not None and client_data.is_secure
        return secure

    def get_client_data(self, attr_name: str) -> Optional[ClientFieldData]:
        return self._hb_config.__fields__[attr_name].field_info.extra.get("client_data")

    def get_description(self, attr_name: str) -> str:
        return self._hb_config.__fields__[attr_name].field_info.description

    def generate_yml_output_str_with_comments(self) -> str:
        original_fragments = yaml.safe_dump(self._dict_in_conf_order(), sort_keys=False).split("\n")
        fragments_with_comments = [self._generate_title()]
        self._add_model_fragments(fragments_with_comments, original_fragments)
        fragments_with_comments.append("\n")  # EOF empty line
        yml_str = "".join(fragments_with_comments)
        return yml_str

    def validate_model(self) -> List[str]:
        results = validate_model(type(self._hb_config), json.loads(self._hb_config.json()))
        self._hb_config = self._hb_config.__class__.construct()
        for key, value in results[0].items():
            self.setattr_no_validation(key, value)
        errors = results[2]
        validation_errors = []
        if errors is not None:
            errors = errors.errors()
            validation_errors = [
                f"{'.'.join(e['loc'])} - {e['msg']}"
                for e in errors
            ]
        return validation_errors

    @contextlib.contextmanager
    def _disable_validation(self):
        self._hb_config.Config.validate_assignment = False
        yield
        self._hb_config.Config.validate_assignment = True

    def _dict_in_conf_order(self) -> Dict[str, Any]:
        d = {}
        for attr in self._hb_config.__fields__.keys():
            value = getattr(self, attr)
            if isinstance(value, ClientConfigAdapter):
                value = value._dict_in_conf_order()
            d[attr] = value
        return d

    def _generate_title(self) -> str:
        title = f"{self._hb_config.Config.title}"
        title = self._adorn_title(title)
        return title

    @staticmethod
    def _adorn_title(title: str) -> str:
        if title:
            title = f"###   {title} config   ###"
            title_len = len(title)
            title = f"{'#' * title_len}\n{title}\n{'#' * title_len}"
        return title

    def _add_model_fragments(
        self,
        fragments_with_comments: List[str],
        original_fragments: List[str],
    ):
        for i, traversal_item in enumerate(self.traverse()):
            attr_comment = traversal_item.field_info.description
            if attr_comment is not None:
                comment_prefix = f"\n{' ' * 2 * traversal_item.depth}# "
                attr_comment = "".join(f"{comment_prefix}{c}" for c in attr_comment.split("\n"))
                if traversal_item.depth == 0:
                    attr_comment = f"\n{attr_comment}"
                fragments_with_comments.extend([attr_comment, f"\n{original_fragments[i]}"])
            elif traversal_item.depth == 0:
                fragments_with_comments.append(f"\n\n{original_fragments[i]}")
            else:
                fragments_with_comments.append(f"\n{original_fragments[i]}")


def parse_cvar_value(cvar: ConfigVar, value: Any) -> Any:
    """
    Based on the target type specified in `ConfigVar.type_str`, parses a string value into the target type.
    :param cvar: ConfigVar object
    :param value: User input from running session or from saved `yml` files. Type is usually string.
    :return: value in the correct type
    """
    if value is None:
        return None
    elif cvar.type == 'str':
        return str(value)
    elif cvar.type == 'list':
        if isinstance(value, str):
            if len(value) == 0:
                return []
            filtered: filter = filter(lambda x: x not in ['[', ']', '"', "'"], list(value))
            value = "".join(filtered).split(",")  # create csv and generate list
            return [s.strip() for s in value]  # remove leading and trailing whitespaces
        else:
            return value
    elif cvar.type == 'json':
        if isinstance(value, str):
            value_json = value.replace("'", '"')  # replace single quotes with double quotes for valid JSON
            cvar_value = json.loads(value_json)
        else:
            cvar_value = value
        return cvar_json_migration(cvar, cvar_value)
    elif cvar.type == 'float':
        try:
            return float(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not valid float.", exc_info=True)
            return value
    elif cvar.type == 'decimal':
        try:
            return Decimal(str(value))
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not valid decimal.", exc_info=True)
            return value
    elif cvar.type == 'int':
        try:
            return int(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not an integer.", exc_info=True)
            return value
    elif cvar.type == 'bool':
        if isinstance(value, str) and value.lower() in ["true", "yes", "y"]:
            return True
        elif isinstance(value, str) and value.lower() in ["false", "no", "n"]:
            return False
        else:
            return value
    else:
        raise TypeError


def cvar_json_migration(cvar: ConfigVar, cvar_value: Any) -> Any:
    """
    A special function to migrate json config variable when its json type changes, for paper_trade_account_balance
    and min_quote_order_amount (deprecated), they were List but change to Dict.
    """
    if cvar.key in ("paper_trade_account_balance", "min_quote_order_amount") and isinstance(cvar_value, List):
        results = {}
        for item in cvar_value:
            results[item[0]] = item[1]
        return results
    return cvar_value


def parse_cvar_default_value_prompt(cvar: ConfigVar) -> str:
    """
    :param cvar: ConfigVar object
    :return: text for default value prompt
    """
    if cvar.default is None:
        default = ""
    elif callable(cvar.default):
        default = cvar.default()
    elif cvar.type == 'bool' and isinstance(cvar.prompt, str) and "Yes/No" in cvar.prompt:
        default = "Yes" if cvar.default else "No"
    else:
        default = str(cvar.default)
    if isinstance(default, Decimal):
        default = "{0:.4f}".format(default)
    return default


async def copy_strategy_template(strategy: str) -> str:
    """
    Look up template `.yml` file for a particular strategy in `hummingbot/templates` and copy it to the `conf` folder.
    The file name is `conf_{STRATEGY}_strategy_{INDEX}.yml`
    :return: The newly created file name
    """
    old_path = get_strategy_template_path(strategy)
    i = 0
    new_fname = f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml"
    new_path = join(CONF_FILE_PATH, new_fname)
    while isfile(new_path):
        new_fname = f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml"
        new_path = join(CONF_FILE_PATH, new_fname)
        i += 1
    shutil.copy(old_path, new_path)
    return new_fname


def get_strategy_template_path(strategy: str) -> str:
    """
    Given the strategy name, return its template config `yml` file name.
    """
    return join(TEMPLATE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_TEMPLATE.yml")


def get_eth_wallet_private_key() -> Optional[str]:
    ethereum_wallet = global_config_map.get("ethereum_wallet").value
    if ethereum_wallet is None or ethereum_wallet == "":
        return None
    private_key = Security._private_keys[ethereum_wallet]
    account = Account.privateKeyToAccount(private_key)
    return account.privateKey.hex()


def _merge_dicts(*args: Dict[str, ConfigVar]) -> OrderedDict:
    """
    Helper function to merge a few dictionaries into an ordered dictionary.
    """
    result: OrderedDict[any] = OrderedDict()
    for d in args:
        result.update(d)
    return result


def get_connector_class(connector_name: str) -> Callable:
    conn_setting = AllConnectorSettings.get_connector_settings()[connector_name]
    mod = __import__(conn_setting.module_path(),
                     fromlist=[conn_setting.class_name()])
    return getattr(mod, conn_setting.class_name())


def get_strategy_config_map(
    strategy: str
) -> Optional[Union[ClientConfigAdapter, Dict[str, ConfigVar]]]:
    """
    Given the name of a strategy, find and load strategy-specific config map.
    """
    config_map = None
    try:
        config_cls = get_strategy_pydantic_config_cls(strategy)
        if config_cls is None:  # legacy
            cm_key = f"{strategy}_config_map"
            strategy_module = __import__(f"hummingbot.strategy.{strategy}.{cm_key}",
                                         fromlist=[f"hummingbot.strategy.{strategy}"])
            config_map = getattr(strategy_module, cm_key)
        else:
            hb_config = config_cls.construct()
            config_map = ClientConfigAdapter(hb_config)
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)
    return config_map


def get_strategy_starter_file(strategy: str) -> Callable:
    """
    Given the name of a strategy, find and load the `start` function in
    `hummingbot/strategy/{STRATEGY_NAME}/start.py` file.
    """
    if strategy is None:
        return lambda: None
    try:
        strategy_module = __import__(f"hummingbot.strategy.{strategy}.start",
                                     fromlist=[f"hummingbot.strategy.{strategy}"])
        return getattr(strategy_module, "start")
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)


def strategy_name_from_file(file_path: str) -> str:
    data = read_yml_file(file_path)
    strategy = data.get("strategy")
    return strategy


def validate_strategy_file(file_path: str) -> Optional[str]:
    if not isfile(file_path):
        return f"{file_path} file does not exist."
    strategy = strategy_name_from_file(file_path)
    if strategy is None:
        return "Invalid configuration file or 'strategy' field is missing."
    if strategy not in get_strategy_list():
        return "Invalid strategy specified in the file."
    return None


def read_yml_file(yml_path: str) -> Dict[str, Any]:
    with open(yml_path, "r") as file:
        data = yaml.safe_load(file) or {}
    return dict(data)


def get_strategy_pydantic_config_cls(strategy_name: str) -> Optional[ModelMetaclass]:
    pydantic_cm_class = None
    try:
        pydantic_cm_pkg = f"{strategy_name}_config_map_pydantic"
        if isfile(f"{root_path()}/hummingbot/strategy/{strategy_name}/{pydantic_cm_pkg}.py"):
            pydantic_cm_class_name = f"{''.join([s.capitalize() for s in strategy_name.split('_')])}ConfigMap"
            pydantic_cm_mod = __import__(f"hummingbot.strategy.{strategy_name}.{pydantic_cm_pkg}",
                                         fromlist=[f"{pydantic_cm_class_name}"])
            pydantic_cm_class = getattr(pydantic_cm_mod, pydantic_cm_class_name)
    except ImportError:
        logging.getLogger().exception(f"Could not import Pydantic configs for {strategy_name}.")
    return pydantic_cm_class


async def load_strategy_config_map_from_file(yml_path: str) -> Union[ClientConfigAdapter, Dict[str, ConfigVar]]:
    strategy_name = strategy_name_from_file(yml_path)
    config_cls = get_strategy_pydantic_config_cls(strategy_name)
    if config_cls is None:  # legacy
        config_map = get_strategy_config_map(strategy_name)
        template_path = get_strategy_template_path(strategy_name)
        await load_yml_into_cm_legacy(yml_path, template_path, config_map)
    else:
        config_data = read_yml_file(yml_path)
        hb_config = config_cls.construct()
        config_map = ClientConfigAdapter(hb_config)
        for key in config_map.keys():
            if key in config_data:
                config_map.setattr_no_validation(key, config_data[key])
        try:
            config_map.validate_model()  # try to coerce the values to the appropriate type
        except Exception:
            pass  # but don't raise if it fails
    return config_map


async def load_yml_into_cm_legacy(yml_path: str, template_file_path: str, cm: Dict[str, ConfigVar]):
    try:
        data = {}
        conf_version = -1
        if isfile(yml_path):
            with open(yml_path) as stream:
                data = yaml_parser.load(stream) or {}
                conf_version = data.get("template_version", 0)

        with open(template_file_path, "r") as template_fd:
            template_data = yaml_parser.load(template_fd)
            template_version = template_data.get("template_version", 0)

        for key in template_data:
            if key in {"template_version"}:
                continue

            cvar = cm.get(key)
            if cvar is None:
                logging.getLogger().error(f"Cannot find corresponding config to key {key} in template.")
                continue

            # Skip this step since the values are not saved in the yml file
            if cvar.is_secure:
                cvar.value = Security.decrypted_value(key)
                continue

            val_in_file = data.get(key, None)
            if (val_in_file is None or val_in_file == "") and cvar.default is not None:
                cvar.value = cvar.default
                continue

            # Todo: the proper process should be first validate the value then assign it
            cvar.value = parse_cvar_value(cvar, val_in_file)
            if cvar.value is not None:
                err_msg = await cvar.validate(str(cvar.value))
                if err_msg is not None:
                    # Instead of raising an exception, simply skip over this variable and wait till the user is prompted
                    logging.getLogger().error(
                        "Invalid value %s for config variable %s: %s" % (val_in_file, cvar.key, err_msg)
                    )
                    cvar.value = None

        if conf_version < template_version:
            # delete old config file
            if isfile(yml_path):
                unlink(yml_path)
            # copy the new file template
            shutil.copy(template_file_path, yml_path)
            # save the old variables into the new config file
            save_to_yml_legacy(yml_path, cm)
    except Exception as e:
        logging.getLogger().error("Error loading configs. Your config file may be corrupt. %s" % (e,),
                                  exc_info=True)


async def read_system_configs_from_yml():
    """
    Read global config and selected strategy yml files and save the values to corresponding config map
    If a yml file is outdated, it gets reformatted with the new template
    """
    await load_yml_into_cm_legacy(GLOBAL_CONFIG_PATH, join(TEMPLATE_PATH, "conf_global_TEMPLATE.yml"), global_config_map)
    await load_yml_into_cm_legacy(TRADE_FEES_CONFIG_PATH, join(TEMPLATE_PATH, "conf_fee_overrides_TEMPLATE.yml"),
                                  fee_overrides_config_map)
    # In case config maps get updated (due to default values)
    save_system_configs_to_yml()


def save_system_configs_to_yml():
    save_to_yml_legacy(GLOBAL_CONFIG_PATH, global_config_map)
    save_to_yml_legacy(TRADE_FEES_CONFIG_PATH, fee_overrides_config_map)


def save_to_yml_legacy(yml_path: str, cm: Dict[str, ConfigVar]):
    """
    Write current config saved a single config map into each a single yml file
    """
    try:
        with open(yml_path) as stream:
            data = yaml_parser.load(stream) or {}
            for key in cm:
                cvar = cm.get(key)
                if cvar.is_secure:
                    Security.update_secure_config(key, cvar.value)
                    if key in data:
                        data.pop(key)
                elif type(cvar.value) == Decimal:
                    data[key] = float(cvar.value)
                else:
                    data[key] = cvar.value
            with open(yml_path, "w+") as outfile:
                yaml_parser.dump(data, outfile)
    except Exception as e:
        logging.getLogger().error("Error writing configs: %s" % (str(e),), exc_info=True)


def save_to_yml(yml_path: str, cm: ClientConfigAdapter):
    try:
        cm_yml_str = cm.generate_yml_output_str_with_comments()
        with open(yml_path, "w+") as outfile:
            outfile.write(cm_yml_str)
    except Exception as e:
        logging.getLogger().error("Error writing configs: %s" % (str(e),), exc_info=True)


async def write_config_to_yml(strategy_name, strategy_file_name):
    strategy_config_map = get_strategy_config_map(strategy_name)
    strategy_file_path = join(CONF_FILE_PATH, strategy_file_name)
    if isinstance(strategy_config_map, ClientConfigAdapter):
        save_to_yml(strategy_file_path, strategy_config_map)
    else:
        save_to_yml_legacy(strategy_file_path, strategy_config_map)
    save_to_yml_legacy(GLOBAL_CONFIG_PATH, global_config_map)


async def create_yml_files_legacy():
    """
    Copy `hummingbot_logs.yml` and `conf_global.yml` templates to the `conf` directory on start up
    """
    for fname in listdir(TEMPLATE_PATH):
        if "_TEMPLATE" in fname and CONF_POSTFIX not in fname:
            stripped_fname = fname.replace("_TEMPLATE", "")
            template_path = join(TEMPLATE_PATH, fname)
            conf_path = join(CONF_FILE_PATH, stripped_fname)
            if not isfile(conf_path):
                shutil.copy(template_path, conf_path)

            # Only overwrite log config. Updating `conf_global.yml` is handled by `read_configs_from_yml`
            if conf_path.endswith("hummingbot_logs.yml"):
                with open(template_path, "r") as template_fd:
                    template_data = yaml_parser.load(template_fd)
                    template_version = template_data.get("template_version", 0)
                with open(conf_path, "r") as conf_fd:
                    conf_version = 0
                    try:
                        conf_data = yaml_parser.load(conf_fd)
                        conf_version = conf_data.get("template_version", 0)
                    except Exception:
                        pass
                if conf_version < template_version:
                    shutil.copy(template_path, conf_path)


def default_strategy_file_path(strategy: str) -> str:
    """
    Find the next available file name.
    :return: a default file name - `conf_{short_strategy}_{INDEX}.yml` e.g. 'conf_pure_mm_1.yml'
    """
    i = 1
    new_fname = f"{CONF_PREFIX}{short_strategy_name(strategy)}_{i}.yml"
    new_path = join(CONF_FILE_PATH, new_fname)
    while isfile(new_path):
        new_fname = f"{CONF_PREFIX}{short_strategy_name(strategy)}_{i}.yml"
        new_path = join(CONF_FILE_PATH, new_fname)
        i += 1
    return new_fname


def short_strategy_name(strategy: str) -> str:
    if strategy == "pure_market_making":
        return "pure_mm"
    elif strategy == "cross_exchange_market_making":
        return "xemm"
    elif strategy == "arbitrage":
        return "arb"
    else:
        return strategy


def all_configs_complete(strategy):
    strategy_map = get_strategy_config_map(strategy)
    return config_map_complete(global_config_map) and config_map_complete(strategy_map)


def config_map_complete(config_map):
    return not any(c.required and c.value is None for c in config_map.values())


def missing_required_configs_legacy(config_map):
    return [c for c in config_map.values() if c.required and c.value is None and not c.is_connect_key]


def load_secure_values(config_map):
    for key, config in config_map.items():
        if config.is_secure:
            config.value = Security.decrypted_value(key)


def format_config_file_name(file_name):
    if "." not in file_name:
        return file_name + ".yml"
    return file_name


def parse_config_default_to_text(config: ConfigVar) -> str:
    """
    :param config: ConfigVar object
    :return: text for default value prompt
    """
    if config.default is None:
        default = ""
    elif callable(config.default):
        default = config.default()
    elif config.type == 'bool' and isinstance(config.prompt, str) and "Yes/No" in config.prompt:
        default = "Yes" if config.default else "No"
    else:
        default = str(config.default)
    if isinstance(default, Decimal):
        default = "{0:.4f}".format(default)
    return default


def retrieve_validation_error_msg(e: ValidationError) -> str:
    return e.errors().pop()["msg"]
