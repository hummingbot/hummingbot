# Troubleshooting

## Installed with Docker

Frequently asked questions and problems that may arise when using Hummingbot with Docker:

#### How do I find out where the config and log files are on my local computer?

Run the following command to view the details of your instance:

```
docker inspect $instance_name
```

Look for a field `Mounts`, which will describe where the folders are on you local machine:

```
"Mounts": [
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_conf",
        "Destination": "/conf",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    },
    {
        "Type": "bind",
        "Source": "/home/ubuntu/hummingbot_files/hummingbot_logs",
        "Destination": "/logs",
        "Mode": "",
        "RW": true,
        "Propagation": "rprivate"
    }
],
```

#### How do I edit the conf files or access the log files used by my docker instance?

You can access the files from your local file system, in the `hummingbot_conf` and `hummingbot_logs` folders on your machine.  The docker instance reads from/writes to these local files.

#### Common Errors with Windows + Docker

Windows users may encounter the following error when running the Docker Toolbox for Windows:

```
C:\Program Files\Docker Toolbox\docker.exe: Error response from daemon: Get https://registry-1.docker.io/v2/: net/http: request canceled while waiting for connection (Client.Timeout exceeded while awaiting headers).
See 'C:\Program Files\Docker Toolbox\docker.exe run --help'.
```

This appears to be an environment configuration problem. The solution is to refresh the environment settings and restart the environment which can be done with the following commands:

```
docker-machine restart default      # Restart the environment
eval $(docker-machine env default)  # Refresh your environment settings
```

#### How do I copy and paste in Docker Toolbox (Windows)?

By default, the Docker Toolbox has copy and paste disabled within the command line. This can make it difficult to port long API and wallet keys to Hummingbot. However, there is a simple fix which can be enabled as follows:

* Open up the Docker Toolbox via the Quickstart Terminal

![](/assets/img/docker_toolbox_startup.PNG)

* Right-click on the title bar of Toolbox and select "Properties"

![](/assets/img/docker_toolbox_properties.png)

* Check the box under the "Options" tab to enable "Ctrl Key Shortcuts"

![](/assets/img/docker_toolbox_enable.png)

Close any warnings, and you're done! Just hit enter to move onto the next line and you should be able to copy and paste text using **Ctrl+Shift+C** and **Ctrl+Shift+V**.

#### How do I update Hummingbot after I had previously installed using old instructions?

If you have previously installed Hummingbot using Docker and our previous documentation naming conventions, can you copy and paste the following command to update to the latest naming as well as to enable the user scripts:

Copy the commands below and run from the root folder (i.e. when you type `ls`, make sure you see the `my-hummingbot` folder).

* If your previous instance was named `my-hummingbot` (check by running `docker ps -a`):

```
# Remove instance
docker rm my-hummingbot && \
# Remove old image
docker image rm coinalpha/hummingbot:latest && \
# Rename file folder
sudo mv my-hummingbot hummingbot_files && \
# Start new instance
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

* If your previous instance was named `my-instance-1` (check by running `docker ps -a`):

```
# Remove instance
docker rm my-instance-1 && \
# Remove old image
docker image rm coinalpha/hummingbot:latest && \
# Rename file folder
sudo mv my-hummingbot hummingbot_files && \
# Start new instance
docker run -it \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

You will then be able to use the [automated docker scripts](/cheatsheets/docker/#automated-docker-scripts-optional).



## Common errors with installed from source

#### conda: not found

```
$ conda
-bash: conda: command not found
```

If you have just installed conda, close terminal and reopen a new terminal to update the command line's program registry.

If you use `zshrc` or another shell other than `bash`, see the note at the bottom of this section: [install dependencies](/installation/from-source/macos/#part-1-install-dependencies).

#### Cannot start Hummingbot

##### Error message:

```
File "bin/hummingbot.py", line 40
  def detect_available_port(starting_port: int) -> int:
                                           ^
SyntaxError: invalid syntax
```

Make sure you have activated the conda environment: `conda activate hummingbot`.

##### Error message:

```
ModuleNotFoundError: No module named 'hummingbot.market.market_base'
```

Make sure you have compiled Hummingbot in the Hummingbot environment: `conda activate hummingbot && ./compile`.


## Running Hummingbot

Coming soon.
