# Troubleshooting

## **Common errors with Hummingbot installed via Docker**

#### Permission denied after installation

```
docker: Got permission denied while trying to connect to the Docker daemon socket at
unix:///var/run/docker.sock: Post
http://%2Fvar%2Frun%2Fdocker.sock/v1.39/containers/create?name=hummingbot_instance:
dial unix /var/run/docker.sock: connect: permission denied.
```

Exit from your virtual machine and restart.


## **Common errors with Hummingbot installed from source**

#### Conda command not found

```
$ conda
-bash: conda: command not found
```

If you have just installed conda, close terminal and reopen a new terminal to update the command line's program registry.

If you use `zshrc` or another shell other than `bash`, see the note at the bottom of this section: [install dependencies](/installation/from-source/macos/#part-1-install-dependencies).

#### Cannot start Hummingbot

##### Syntax error invalid syntax

```
File "bin/hummingbot.py", line 40
  def detect_available_port(starting_port: int) -> int:
                                           ^
SyntaxError: invalid syntax
```

Make sure you have activated the conda environment: `conda activate hummingbot`.

##### Module not found error

```
ModuleNotFoundError: No module named 'hummingbot.market.market_base'

root - ERROR - No module named
‘hummingbot.strategy.pure_market_making.inventory_skew_single_size_sizing_delegate’
(See log file for stack trace dump)
```

Exit Hummingbot to compile and restart using these commands:

```bash
conda activate hummingbot
./compile
bin/hummingbot.py
```

## **Common Errors with Windows + Docker Toolbox**

Windows users may encounter the following error when running the Docker Toolbox for Windows:

```
C:\Program Files\Docker Toolbox\docker.exe:
Error response from daemon: Get https://registry-1.docker.io/v2/:net/http: request canceled while waiting for connection
(Client.Timeout exceeded while awaiting headers).
See 'C:\Program Files\Docker Toolbox\docker.exe run --help'.
```

This appears to be an environment configuration problem. The solution is to refresh the environment settings and restart the environment which can be done with the following commands:

```bash
# Restart the environment
docker-machine restart default

# Refresh your environment settings
eval $(docker-machine env default)
```

## **Errors while running Hummingbot**

#### Binance errors in logs

These are known issues from the Binance API and Hummingbot will attempt to reconnect afterwards.

```
hummingbot.market.binance.binance_market - NETWORK - Unexpected error while fetching account updates.

AttributeError: 'ConnectionError' object has no attribute 'code'
AttributeError: 'TimeoutError' object has no attribute 'code'

hummingbot.core.utils.async_call_scheduler - WARNING - API call error:
('Connection aborted.', OSError("(104, 'ECONNRESET')",))

hummingbot.market.binance.binance_market - NETWORK - Error fetching trades update for the order
[BASE]USDT: ('Connection aborted.', OSError("(104, 'ECONNRESET')",)).
```

!!! note
    Hummingbot should run normally regardless of these errors. If the bot fails to perform or behave as expected (e.g. placing and cancelling orders, performing trades, stuck orders, orders not showing in exchange, etc.) you can get help through our [support channels](/support/index).


#### IDEX errors in logs

You may see any of these errors in logs when trading on IDEX market. These are server-side issues on IDEX's end.

```
OSError: Error fetching data from https://api.idex.market/order.

HTTP status is 400 - {'error': "Cannot destructure property `tier` of 'undefined' or 'null'."}
HTTP status is 400 - {'error': 'Unauthorized'}
HTTP status is 400 - {'error': 'Nonce too low. Please refresh and try again.'}
HTTP status is 500 - {'error': 'Something went wrong. Try again in a moment.'}
```

!!! note
    Hummingbot should run normally regardless of these errors. If the bot fails to perform or behave as expected (e.g. placing and cancelling orders, performing trades, stuck orders, orders not showing in exchange, etc.) you can get help through our [support channels](/support/index).


## **Common 'How To' Questions**

Frequently asked questions and problems that may arise when using Hummingbot with Docker:

#### How do I find out where the config and log files are on my local computer?

Run the following command to view the details of your instance:

```bash
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

If Hummingbot is installed on your local machine, you can access the files from your local file system in the `hummingbot_conf` and `hummingbot_logs` folder. The docker instance reads from/writes to these local files.

If Hummingbot is installed on a virtual machine, you can use the `vi` text editor (or any text editor of your choice). Do command `vi $filename`. See [this page](https://www.tipsandtricks-hq.com/unix-vi-commands-take-advantage-of-the-unix-vi-editor-374) for more information how to use this text editor.

You can also use an FTP client software (e.g. WinSCP, FileZila) to copy, move, files and folders from your virtual machine to your local machine and vice versa.


#### How do I copy and paste in Docker Toolbox (Windows)?

By default, the Docker Toolbox has copy and paste disabled within the command line. This can make it difficult to port long API and wallet keys to Hummingbot. However, there is a simple fix which can be enabled as follows:

1. Open up the Docker Toolbox via the Quickstart Terminal

  ![](/assets/img/docker_toolbox_startup.PNG)

2. Right-click on the title bar of Toolbox and select "Properties"

  ![](/assets/img/docker_toolbox_properties.png)

3. Check the box under the "Options" tab to enable "Ctrl Key Shortcuts"

  ![](/assets/img/docker_toolbox_enable.png)


Close any warnings, and you're done! Just hit enter to move onto the next line and you should be able to copy and paste text using **Ctrl+Shift+C** and **Ctrl+Shift+V**.


#### How do I paste items from clipboard in PuTTY?

You should be able to paste items from your clipboard by doing `SHIFT + right-click`. If that doesn't work, follow the steps below.

1. If you are currently logged in a session, do a left-click on the upper left hand corner of the PuTTY window or a right-click anywhere on the title bar then select "Change Settings". If not, proceed to step 2.

  ![](/assets/img/putty_1.png)

2. In PuTTY configuration under Window category go to "Selection". Select the "Window" radio button for action of mouse buttons.

  ![](/assets/img/putty_2.png)

3. You can now paste items from clipboard by doing a right-click to bring up the menu and select "Paste".

  ![](/assets/img/putty_3.png)



#### How do I update Hummingbot after I had previously installed using old instructions?

If you have previously installed Hummingbot using Docker and our previous documentation naming conventions, can you copy and paste the following command to update to the latest naming as well as to enable the user scripts:

Copy the commands below and run from the root folder (i.e. when you type `ls`, make sure you see the `my-hummingbot` folder).

* If your previous instance was named `my-hummingbot` (check by running `docker ps -a`):

```bash
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

```bash
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
