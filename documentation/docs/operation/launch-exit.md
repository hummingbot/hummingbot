# Launch and Exit Hummingbot

This page contains information on launching and exiting the application, assuming Hummingbot is installed already on your machine.

## Launch via Docker

If you downloaded the helper script before, proceed to step 2.

1. Download `start.sh` helper script from Github using the command below.

```Manual
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
chmod a+x start.sh
```

!!! tip
    Run `ls` command from the terminal to check if the file is in your current directory.

2. Run the following command inside the directory where the helper script is located:

```Manual
./start.sh
```

![](/assets/img/launch-via-docker.gif)

!!! tip
    If no containers are running, follow the guide to creating a Hummingbot instance.

## Launch from source

1. Make sure the hummingbot conda environment is enabled.

```Manual
conda activate hummingbot
```

2. In the `hummingbot` parent directory, run this command to launch the application:

```Manual
bin/hummingbot.py
```

![](/assets/img/launch-from-source.gif)

## Exit Hummingbot

Running the `exit` command cancels all outstanding orders and exit the Hummingbot interface. In case of errors, the command `exit -f` will force the application to close.

If you're running Hummingbot installed via binary, exiting Hummingbot by clicking the close window icon will leave your active orders open in the exchange.

!!! tip
    You can also press the keyboard shortcut `CTRL + C` twice to exit.
