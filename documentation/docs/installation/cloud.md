# Install on Google Cloud Platform

Running `hummingbot` as a long running service can be achieved with the help of Google Cloud Platform.

## Setup a new VM instance on Google Cloud Platform 

   * Navigate to the Google Cloud Platform console
   * Create an instance of Compute Instance
   * Select “New VM Instance”, then pick `Ubuntu 18.04 LTS`
    
   ![Create New Instance](/assets/img/gcp-new-vm.png)
   
   * Click on "SSH" to SSH into the newly created VM instance 

![Connect SSH](/assets/img/gcp-ssh.png)

## Install Docker on Ubuntu (or refer to [Docker official instructions](https://docs.docker.com/install/linux/docker-ce/ubuntu/))

   * Update the apt package index

```
sudo apt-get update
```

   * Install packages to allow apt to use a repository over HTTPS

```
sudo apt-get install \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common
```

   * Add Docker’s official GPG key, fingerprint, and repository

```
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo apt-key fingerprint 0EBFCD88
sudo add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) \
    stable"
```

   * Do another apt-get update

```
sudo apt-get update
```

   * Install Docker

```
sudo apt-get install docker-ce docker-ce-cli containerd.io
```

## Install Hummingbot from Docker

   * Run the following command

```
export NAME=myhummingbot
export TAG=latest
sudo docker run -it \
--name $NAME \
-v "$PWD"/conf/:/conf/ \
-v "$PWD"/logs/:/logs/ \
coinalpha/hummingbot:$TAG
```

![Installing Hummingbot from Docker](/assets/img/gcp-ssh-docker-installing.png)

   * After docker completion installed, you’ll see the following screen, where Hummingbot successfully starts

![Hummingbot Welcome Screen](/assets/img/gcp-ssh-hummingbot.png)

Start market making!
