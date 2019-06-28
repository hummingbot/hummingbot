# Windows Installation from Docker

## Installing Hummingbot via the Docker Toolbox

For Windows users without Windows-Pro or Windows-Enterprise, you will need to install the Docker Toolbox, as Windows-Home is not supported by the standard Docker application. Below, we list instructions for running Hummingbot using the Docker Toolbox.

### 1. Install Docker Toolbox

Download the latest version Docker Toolbox .exe file at the following link: [Docker Toolbox Releases](https://github.com/docker/toolbox/releases/).

![Docker Download](/assets/img/docker_toolbox_download.PNG)

Locate the installer in the downloads folder and run a full installation with included VirtualBox and Git for Windows. (Git is the default shell used by Docker)

![Docker Installation](/assets/img/docker_toolbox_install.PNG)

By default, a shortcut to the Docker Quickstart terminal will be created on your desktop. You can open Docker Toolbox using this shortcut.

![Docker Startup](/assets/img/docker_toolbox_startup.PNG)

### 2. Run Hummingbot

Open Docker Toolbox using the Quickstart shortcut. It may take a few minutes to initialize. Move onto the next step when you reach the following screen.

![Docker Ready](/assets/img/docker_toolbox_cmdline.PNG)

Once Docker is ready, you can proceed to the [Hummingbot installation commands](/installation/docker/#install-hummingbot).
