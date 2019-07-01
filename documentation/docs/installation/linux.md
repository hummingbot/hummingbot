# Linux Source Installation

Hummingbot has been tested on [Ubuntu](https://ubuntu.com/), [Debian](https://www.debian.org/), and [CentOS](https://www.centos.org/) distributions of Linux.

In the instructions below, we are using [Miniconda3](), a lighter version of [Anaconda]() which is sufficient to run Hummingbot.  To learn more about the differences and what works best for you, see [this post](http://deeplearning.lipingyang.org/2018/12/23/anaconda-vs-miniconda-vs-virtualenv/).

## Install Commands for Ubuntu

```
# 1) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Log out and log back into shell to register "conda" command
exit
# Log back into or open a new Linux terminal

# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 5) Install Hummingbot
cd hummingbot && ./install

# 6) Activate environment and compile code
conda activate hummingbot && ./compile

# 7) Start Hummingbot
bin/hummingbot.py
```

## Install Commands for Debian

```
# 1) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential git

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Log out and log back into shell to register "conda" command
exit
# Log back into or open a new Linux terminal

# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 5) Install Hummingbot
cd hummingbot && ./install

# 6) Activate environment and compile code
conda activate hummingbot && ./compile

# 7) Start Hummingbot
bin/hummingbot.py
```

## Install Commands for CentOS

```
# 1) Install dependencies
sudo yum install -y wget bzip2 git
sudo yum groupinstall -y 'Development Tools'

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Log out and log back into shell to register "conda" command
exit
# Log back into or open a new Linux terminal

# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 5) Install Hummingbot
cd hummingbot && ./install

# 6) Activate environment and compile code
conda activate hummingbot && ./compile

# 7) Start Hummingbot
bin/hummingbot.py
```
