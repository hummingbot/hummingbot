# Troubleshooting

## Installed with Docker

Frequently asked questions and problems that may arise when using Hummingbot with Docker:

#### How do I find out the name of my hummingbot instance?

Run the following command to list all docker instances you have created:

```
docker ps -a
```

#### How do I list all the containers I have created?

```
docker ps -a
```

#### How do I check that my Hummingbot instance is running?

The following command will list all currently running docker containers:

```
docker ps
```

#### How do I find out where the config and log files are on my local computer?

Run the following command to view the details of your instance:

```
docker inspect hummingbot-instance
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

#### How do I connect to my Hummingbot instance?

```
docker attach hummingbot-instance
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

## Installed from source

Coming soon.

## Running Hummingbot

Coming soon.
