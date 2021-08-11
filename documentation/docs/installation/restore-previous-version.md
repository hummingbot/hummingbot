# Restore Previous Version

## Restore to a previous version via Docker

A previous version can be installed when creating a Hummingbot instance.

```
# 1) Run the script to create a hummingbot instance
./create.sh

# 2) Specify the version to be installed when prompted

** ✏️  Creating a new Hummingbot instance **

ℹ️  Press [enter] for default values.

➡️  Enter Hummingbot version: [latest|development] (default = "latest")

```

- Windows/Mac/Linux: For example, enter `version-0.16.0`. The versions are listed here in [Hummingbot Tags](https://hub.docker.com/r/coinalpha/hummingbot/tags).
- Raspberry Pi: For example, enter `dev-0.30.0-arm_beta`. The versions are listed here in [Hummingbot Tags](https://hub.docker.com/r/coinalpha/hummingbot/tags?page=1&name=arm).

## Revert to a previous version via binary

The user can revert and update Hummingbot installed via Binary by following the steps below:

To install a previous Hummingbot version via binary, download the installer from https://hummingbot.io/download/ in the previous client section

![](/assets/img/installer.png)

Users can also download an older version not listed on the website using the URL format `https://dist.hummingbot.io/[hummingbot_version]`

For example:

![](/assets/img/download.png)
