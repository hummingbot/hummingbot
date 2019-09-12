# Logs and Logging

As Hummingbot is an in-progress, open-access software, it is written for logs to be publicly displayed during operation and available locally for each time an instance is run. Logs contain records of what happens when a bot is run, including the results of specified checks and behaviors as well as error tracing.

## Viewing Log Configurations

The way that log files are structured is contained within `conf/hummingbot_logs.yml`. For now, we request that users leave the log settings at the defaults. This makes it easier for the Hummingbot team to trace bugs and other problems that users face when logs are submitted.

## Viewing Individual Log Files

For users who wish to locate and submit log files, they are located in the `/logs` folder. This folder is generally within the main `hummingbot` folder when Hummingbot is installed from source, and in the user-designated instance folder (default `hummingbot-instance`) when it is installed using Docker.

If you are looking for support in handling errors or have questions about behavior reported in logs, you can find ways of contacting the team or community in our [support section](/support).
