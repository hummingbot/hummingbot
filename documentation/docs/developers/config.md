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

| Attribute     | Attribute Type  | Use | 
|-------------- | --------------- | --- |
| `key`         | str             | Unique key that identifies a config variable. |
| `prompt`      | str or callable | Question displayed in the client when the bot collects user input for this config setting. You can modify the string in run time by passing a function rather than a static string. |
| `is_secure`   | bool            | Whether the user input needs to be masked with "***". |
| `default`     | any             | Default value for this variable if user input is None. |
| `type_str`    | str             | One of {"str", "list", "dict", "float", "int", "bool"}. Defaults to "str". This is used by `parse_cvar_value` to parse user input into correct data type. |
| `required_if` | callable        | A condition check for whether this config setting needs to be prompted during the configuration flow. |
| `validator`   | callable        | A condition check for whether an input is a valid value for this config setting. |
| `on_validated`| callable        | A function hook that gets activated if an input passes the validation check (e.g. set wallet requirement to True when a valid DEX name is entered.) |

Check `hummingbot/client/config/config_var.py` for more details.

### Config definition conventions
1. Always place configs that will alters requirement state first. 
   Example: `telegram_token` should only be required if `telegram_enabled` is set to True. Therefore `telegram_enabled` should be listed before `telegram_token`.
2. For exchange-specific configurations, use `using_exchange("exchange_name")` as the `required_if` condition.
3. When writing prompt questions, be sure to add examples for a better user experience.
4. When prompting for a boolean value, add `(Yes/No)` as options so that the user knows what to enter.
5. When prompting a question with a few choices as answers e.g. `["import", "create", etc]`, make sure to include all options in the format of `(OPTION_1/OPTION_2/OPTION_3)`. 
   This pattern is recognized by our autocomplete system, and the user can hit `Tab` to have the option autofilled. 
6. When prompting for an exchange name, make sure to include 'exchange name', 'name of exchange' or 'name of the exchange' in the prompt text (case insensitive, e.g. Exchange Name is valid), our autocomplete system will list and autofill with exchange names supported by our system.
