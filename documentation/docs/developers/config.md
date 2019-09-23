# Configuration Module

Hummingbot's config module helps onboard users who are new to running a trading bot. It is helpful in 
- Compiling a list of absolutely essential config variables.
- Skip or provide default variables that are more advanced / have the potential to confuse new users.
- Collecting and validating user inputs as config values.
- Check if all configs are present before running any strategy.

## Architecture

Currently, we split all the configuration variables into three different types.

| Config type   | In-memory location | Saved to local yml | Description                 |
|-------------- | ------------------ | ------------------ | --------------------------- |
| `in_memory`   | `hummingbot/client/config/in_memory_config_map.py` | No | Configs that are never saved and prompted every time (currently, only the `strategy` and `strategy_config_path` are in this config map.
| `global`      | `hummingbot/client/config/global_config_map.py` | Yes | Strategy-agnostic configs such as exchange API keys, wallet selection, etc.
| `strategy`    | `hummingbot/strategy/{STRATEGY_NAME}/{STRATEGY_NAME}_strategy_config_map.py` | Yes | Strategy-specific configs.


## Default Configuration Flow
1. When the bot starts, it automatically reads all the global configurations from a file named `conf_global.yml`. If 
   such a file does not exist, it will copy the empty template from `hummingbot/templates/conf_global_TEMPLATE.yml`. 
   The bot populates `global_config_map` object in `hummingbot/client/config/global_config_map.py` with any values 
   previously saved in the yml file.
2. When the user enters `config` command, the bot prompts the user all the items in `in_memory_config_map`.
3. Once a user inputs her desired strategy, she can choose to `import` or `create` a configuration file. 
    - if `import` is chosen, the user will be prompted to select a strategy config file. The bot will load all variables values and save them in-memory.
    - if `create` is chosen, the bot will copy a strategy config template from `hummingbot/templates/conf_{STRATEGY_NAME}_strategy_{COUNT}.yml`.
      The user will then fill out each of the configs required by that specific strategy.
4. With each user input, the bot will validate the input with a custom checker (more details on that in the ConfigVar class). If an input is invalid,
    the user is prompted the same question again.
5. After all the strategy configs are filled out, the bot uses the newly acquired info to figure out which variables 
    are require in **global** config settings (Which exchange API keys to prompt, etc).
6. Since altering certain variables will trigger requirement for other variables, this prompt-and-config process loops until all variables are complete.
7. When the loop finishes. The bot writes all of the config variables saved in memory to local `yml` files so that they can be reused for another session.
7. The user can then start running her selected strategy with the set of configs currently stored in memory.


## ConfigVar Class
The ConfigVar Class is located in `hummingbot/client/config/config_var.py`. It standardizes each config setting with a set of attributes.

| Config type   | In-memory location | Saved to local yml | Description                 |
|-------------- | ------------------ | ------------------ | --------------------------- |
| `in_memory`   | `hummingbot/client/config/in_memory_config_map.py` | No | Configs that are never saved and prompted every time (currently, only the `strategy` and `strategy_config_path` are in this config map.
| `global`      | `hummingbot/client/config/global_config_map.py` | Yes | Strategy-agnostic configs such as exchange API keys, wallet selection, etc.
| `strategy`    | `hummingbot/strategy/{STRATEGY_NAME}/{STRATEGY_NAME}_strategy_config_map.py` | Yes | Strategy-specific configs.

## Altering a single config


## Resetting all configs


## Development Tips
1. Always place configs that will alters requirement state first. 
   Example: `telegram_token` should only be required if `telegram_enabled` is set to True. Therefore `telegram_enabled` should be listed before `telegram_token`.