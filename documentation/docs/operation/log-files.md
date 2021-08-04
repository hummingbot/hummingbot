# Log Files

As Hummingbot is an in-progress and open-access software, logs are stored locally in your computer each time an instance is run. While the bot is active, record of status updates, results of specified checks and behaviors, as well as error tracing is encoded in the log files.

### Viewing log configurations

The way that log files are structured is contained within `conf/hummingbot_logs.yml`. For now, we request that users leave the log settings at the defaults. This makes it easier for the Hummingbot team to trace bugs and other problems that users face when logs are submitted.

### Viewing individual log files

For users who wish to locate and submit log files, generally they are located in the `/logs` folder.
Specific path or location may vary depending on the environment and how Hummingbot was installed.

- Installed from source: `hummingbot/logs`
- Installed via Docker: `hummingbot_files/hummingbot_logs`
  - `hummingbot_files` is the default name of the parent directory. This can be different depending on the setup
    when the instance was created.
- Installed via Binary (Windows): `%localappdata%\hummingbot.io\Hummingbot\logs`
- Installed via Binary (MacOS): `~/Library/Application\ Support/Hummingbot/Logs`

### Log file management

A separate log file will now be generated daily. When a new log file is created, if there are more than 7 files,
the oldest ones will be deleted in order to limit disk storage usage.
The log rotation feature was added in [Hummingbot version 0.17.0](https://docs.hummingbot.io/release-notes/0.17.0/#log-file-management-data-storage).

If you are looking for support in handling errors or have questions about behavior reported in logs,
you can find ways of contacting the team or community in our [support section](/intro/support).
