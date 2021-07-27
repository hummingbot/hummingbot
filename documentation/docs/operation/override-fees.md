# Override Fees

By default, Hummingbot uses the default fees of the exchange. However, if you're on a VIP level getting discounts on fees, you can override this by editing the `conf_fee_overrides.yml` inside the `conf` or `hummingbot_conf` directory, depending on your installation method.

- Installed from source: `hummingbot/conf`
- Installed via Docker: `hummingbot_files/hummingbot_conf`
  - `hummingbot_files` is the default name of the parent directory. This can be different depending on the setup
    when the instance was created.
- Installed via Binary (Windows): `%localappdata%\hummingbot.io\Hummingbot\conf`
- Installed via Binary (MacOS): `~/Library/Application\ Support/Hummingbot/Conf`

![](/assets/img/fees-override.png)

!!! note
    Exit and restart Hummingbot for the changes to take effect.
