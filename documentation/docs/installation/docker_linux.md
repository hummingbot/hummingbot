# Linux Installation from Docker

## Install Docker on Ubuntu

```bash="Ubuntu"
# 1) Update Ubuntu's database of software
sudo apt-get update

# 2) Install Docker
sudo apt install -y docker.io

# 3) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker

# 4) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER
# Log out and log back into shell
```

## Install Docker on Debian

```bash="Debian"
# 1) Update package database
sudo apt update

# 2) Install dependencies
sudo apt install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common

# 3) Register Docker repository to your system
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
sudo apt update

# 4) Install Docker
sudo apt install -y docker-ce

# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER
# Log out and log back into shell
```

## Install Docker on CentOS

```bash="CentOS"
# 1) Update package database
sudo yum check-update

# 2) Install Docker
curl -fsSL https://get.docker.com/ | sh

# 3) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker

# 4) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER
# Log out and log back into shell
```

## Run Hummingbot

Once you have Docker installed, you can proceed to the [Hummingbot installation commands](/installation/docker/#install-hummingbot).
