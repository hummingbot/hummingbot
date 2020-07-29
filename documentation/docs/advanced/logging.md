# Logs and Logging

As Hummingbot is an in-progress, open-access software, logs are available locally for each time an instance is run. Logs contain records of what happens when a bot is run, including the results of specified checks and behaviors as well as error tracing.

## Viewing Log Configurations

The way that log files are structured is contained within `conf/hummingbot_logs.yml`. For now, we request that users leave the log settings at the defaults. This makes it easier for the Hummingbot team to trace bugs and other problems that users face when logs are submitted.

## Error Log Collection

The only data Hummingbot requests from users is error logs. We collect error logs for the sole purpose of debugging and continuously improving Hummingbot. We'll never share the data with a third party.

You can choose to disable error logging.

```
Would you like to send error logs to hummingbot? (Yes/No) >>>
```
If the user answers "No", then no data will be collected.

You can always enable/disable sending error logs in two ways:

1. Editing `conf_global.yml` file using a text editor.
1. Inside Hummingbot enter: `config send_error_logs`.


## Viewing Individual Log Files

For users who wish to locate and submit log files, generally they are located in the `/logs` folder. 
Specific path or location may vary depending on the environment and how Hummingbot was installed.

- Installed from source: `hummingbot/logs`
- Installed via Docker: `hummingbot_files/hummingbot_logs`
    - `hummingbot_files` is the default name of the parent directory. This can be different depending on the setup 
    when the instance was created.
- Installed via Binary (Windows): `%localappdata%\hummingbot.io\Hummingbot\logs`
- Installed via Binary (MacOS): `~/Library/Application\ Support/Hummingbot/Logs`

## Log File Management

A separate log file will now be generated daily. When a new log file is created, if there are more than 7 files, 
the oldest ones will be deleted in order to limit disk storage usage. 
The log rotation feature was added in [Hummingbot version 0.17.0](https://docs.hummingbot.io/release-notes/0.17.0/#log-file-management-data-storage).

If you are looking for support in handling errors or have questions about behavior reported in logs, 
you can find ways of contacting the team or community in our [support section](/support).
