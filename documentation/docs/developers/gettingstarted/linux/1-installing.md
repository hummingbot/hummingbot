# Developer Quickstart – Linux | Installing

This section walks you through how to prepare your development environment and install Hummingbot from source manually.

## Ubuntu

*Supported versions: 16.04 LTS, 18.04 LTS, 19.04*

```bash tab="Manual Installation"
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

```bash tab="Manual Installation"
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

```bash tab="Manual Installation"
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

- The installation instructions above use [Miniconda3](https://docs.conda.io/en/latest/miniconda.html), a lighter version of [Anaconda](https://www.anaconda.com/) which is sufficient to run Hummingbot.  To learn more about the differences and what works best for you, see [this post](http://deeplearning.lipingyang.org/2018/12/23/anaconda-vs-miniconda-vs-virtualenv/).


---
# Next: [Using Hummingbot](/developers/gettingstarted/linux/2-using)
