# Linux Source Installation

!!! info "Recommended for Developers Only"
    [Installation using Docker](/installation/docker/linux) is more efficient for running Hummingbot.  Installing from source is only recommended for developers who want to access and modify the software code.

You can install Hummingbot with ***either*** of the following options:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.


## Ubuntu

*Supported versions: 16.04 LTS, 18.04 LTS, 19.04*

```bash tab="Option 1: Easy Install"
# 1) Download install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-source-ubuntu.sh

# 3) Run installation
./install-source-ubuntu.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Reload .bashrc to register "conda" command
exec bash

# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 5) Install Hummingbot
cd hummingbot && ./clean && ./install

# 6) Activate environment and compile code
conda activate hummingbot && ./compile

# 7) Start Hummingbot
bin/hummingbot.py
```

## Debian

*Supported version: Debian GNU/Linux 9*

```bash tab="Option 1: Easy Install"
# 1) Download install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-debian.sh

# 2) Enable script permissions
chmod a+x install-source-debian.sh

# 3) Run installation
./install-source-debian.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Install dependencies
sudo apt-get update
sudo apt-get install -y build-essential git

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Reload .bashrc to register "conda" command
exec bash

# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 5) Install Hummingbot
cd hummingbot && ./clean && ./install

# 6) Activate environment and compile code
conda activate hummingbot && ./compile

# 7) Start Hummingbot
bin/hummingbot.py
```

## CentOS

*Supported version: 7*

```bash tab="Option 1: Easy Install"
# 1) Download install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-centos.sh

# 2) Enable script permissions
chmod a+x install-source-centos.sh

# 3) Run installation
./install-source-centos.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Install dependencies
sudo yum install -y wget bzip2 git
sudo yum groupinstall -y 'Development Tools'

# 2) Install Miniconda3
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
sh Miniconda3-latest-Linux-x86_64.sh

# 3) Reload .bashrc to register "conda" command
exec bash

# 4) Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git

# 5) Install Hummingbot
cd hummingbot && ./clean && ./install

# 6) Activate environment and compile code
conda activate hummingbot && ./compile

# 7) Start Hummingbot
bin/hummingbot.py
```

---

## Developer Notes

- Additional details of the scripts can be found on [Github: Hummingbot Install Scripts](https://github.com/CoinAlpha/hummingbot/tree/development/installation/install-from-source).
- The installation instructions above use [Miniconda3](https://docs.conda.io/en/latest/miniconda.html), a lighter version of [Anaconda](https://www.anaconda.com/) which is sufficient to run Hummingbot.  To learn more about the differences and what works best for you, see [this post](http://deeplearning.lipingyang.org/2018/12/23/anaconda-vs-miniconda-vs-virtualenv/).
