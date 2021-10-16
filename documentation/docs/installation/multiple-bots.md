# Running Multiple Bots

## Multiple bots via binary

Users can run multiple bots of Hummingbot installed via binary by simply running a new instance to open a new window.

![](/assets/img/multiple_bots1.gif)

## Multiple bots via Docker

Create multiple instances using `./create.sh` script. Then, use the following commands to download the create script and make it executable.

**Linux**

```Linux
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
chmod a+x *.sh
```

**MacOS**

```MacOS
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
chmod a+x *.sh
```

**Windows (Docker Toolbox)**

```
cd ~
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh -o create.sh
chmod a+x *.sh
```

## Multiple bots from source

!!! tip
    We recommend that users download and install Hummingbot separately for each instance they wish to run.

The below command downloads the Hummingbot repository from GitHub, where `$FOLDER_NAME` is the name of the separate directory.

```
cd ~
git clone https://github.com/CoinAlpha/hummingbot.git $FOLDER_NAME
```

Do another install in the new directory.

```
cd $FOLDER_NAME
./install
conda activate hummingbot
./compile
```

## Keep bots running in the background

### Docker

Press keys `Ctrl+P` then `Ctrl+Q` in sequence to detach from Docker, i.e., return to the command line. This exits out of Hummingbot without shutting down the container instance.

Restart or connect to a running instance using the `./start.sh` script. Below commands download the start script and make it executable.

### From source

Use either `tmux` or `screen` to run multiple bots installed from source. Check out these external links how to use them.

- [Getting started with Tmux](https://linuxize.com/post/getting-started-with-tmux/)
- [How to use Linux Screen](https://linuxize.com/post/how-to-use-linux-screen/)

When using screen to run an instance in the background, run either of the following commands: `screen` or `screen -S $NAME`, where `$NAME` is what you wish to call this background instance. Use the latter to be more explicit if you want to run multiple bots.

Navigate to the folder where your separate Hummingbot is installed, then start the bot like normal.

```
conda activate hummingbot
bin/hummingbot.py
```

To exit the screen (detach), press `Ctrl+A` then `Ctrl+D` in sequence.

To list all running instances, use `screen -ls`.

![List Screen Instances](/assets/img/screen.png)

Log back into the screen by using either `screen` or `screen -r $NAME` to open a specific instance.

<small>
  Credits to discord user `@matha` for this question and `@pfj` for the
  solution.
</small>
