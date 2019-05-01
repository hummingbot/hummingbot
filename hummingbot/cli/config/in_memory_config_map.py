from os.path import join

from hummingbot.cli.config.config_var import ConfigVar
from hummingbot.cli.config.config_validators import (
    is_strategy,
    is_path,
)
from hummingbot.cli.settings import (
    CONF_FILE_PATH,
    CONF_POSTFIX,
    CONF_PREFIX,
)
from hummingbot.cli.config.config_helpers import (
    load_required_configs,
    read_configs_from_yml,
)


def get_default_strategy_config_yml_path(strategy: str) -> str:
    return join(CONF_FILE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_0.yml")


# Prompt generators
def default_strategy_conf_path_prompt():
    strategy = in_memory_config_map.get("strategy").value
    return "Enter path to your strategy file (e.g. \"%s\") >>> " \
           % (get_default_strategy_config_yml_path(strategy),)


# These configs are never saved and prompted every time
in_memory_config_map = {
    # Always required
    "strategy":                         ConfigVar(key="strategy",
                                                  prompt="What is your market making strategy? >>> ",
                                                  validator=is_strategy,
                                                  on_validated=load_required_configs),
    "strategy_file_path":               ConfigVar(key="strategy_file_path",
                                                  prompt=default_strategy_conf_path_prompt,
                                                  validator=is_path,
                                                  on_validated=read_configs_from_yml)
}