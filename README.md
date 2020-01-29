
Hummingbot for ETERBASE Exchange
## Install Hummingbot
Actual possibility to install it is via source code installation

## [Installation guideline]
#### **Ubuntu** (16.04 LTS, 18.04 LTS, 19.04) & **Debian** (Debian GNU/Linux 9) 

**1. Install dependencies**

`sudo apt-get update`

`sudo apt-get install -y build-essential`

**2. Install Miniconda3**

`wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh`

`sh Miniconda3-latest-Linux-x86_64.sh`

**3. Reload .bashrc to register "conda" command**

`exec bash`

**4. Clone Hummingbot**

`git clone https://github.com/eterbase/hummingbot.git`

**5. Install Hummingbot**

`cd hummingbot && ./clean && ./install`

**6. Activate environment and compile code**

`conda activate hummingbot && ./compile`

**7. Start Hummingbot**

`bin/hummingbot.py`

------------
#### CentOS 7
**1. Install dependencies**

`sudo yum install -y wget bzip2 git`

`sudo yum groupinstall -y 'Development Tools'`

**2. Install Miniconda3**

`wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh`

`sh Miniconda3-latest-Linux-x86_64.sh`

**3. Reload .bashrc to register "conda" command**

`exec bash`

**4. Clone Hummingbot**

`git clone https://github.com/eterbase/hummingbot.git`

**5. Install Hummingbot**

`cd hummingbot && ./clean && ./install`

**6. Activate environment and compile code**

`conda activate hummingbot && ./compile`

**7. Start Hummingbot**

`bin/hummingbot.py`

------------
#### **MacOS**
Running Hummingbot on Mac OSX requires Xcode and Xcode command line tools.

**1. Install Xcode command line tools**

`xcode-select --install`

**2. Install Anaconda3**

Hummingbot requires Python 3 and other Python libraries. To manage these dependencies, Hummingbot uses Anaconda, an open source environment and package manager for Python that is the current industry standard for data scientists and data engineers.

To install Anaconda, go to the Anaconda site and download the Python 3.7 installer for your operating system. Both the graphical installer and the command line installer will work. Run the installer, and it will guide you through the installation process.

Afterwards, open a Terminal window and try the conda command. If the command is valid, then Anaconda has been successfully installed, even if the graphical installer says that it failed.

**Warning**

If you use ZSH or another Unix shell, copy the code snippet below to your .zshrc or similar file. By default, Anaconda only adds it to your .bash_profile file. This makes the conda command available in your root path.
```bash
__conda_setup="$(CONDA_REPORT_ERRORS=false '/anaconda3/bin/conda' shell.bash hook 2> /dev/null)"
if [ $? -eq 0 ]; then
    \eval "$__conda_setup"
else
    if [ -f "/anaconda3/etc/profile.d/conda.sh" ]; then
        . "/anaconda3/etc/profile.d/conda.sh"
        CONDA_CHANGEPS1=false conda activate base
    else
        \export PATH="/anaconda3/bin:$PATH"
    fi
fi
unset __conda_setup
```
**3. Install Hummingbot**

**3.1. Clone Hummingbot repo**

`git clone https://github.com/eterbase/hummingbot.git`

**3.2. Navigate into the hummingbot folder**

`cd hummingbot`

**3.3. Run install script**

`./install`

**3.4. Activate environment**

`conda activate hummingbot`

**3.5. Compile**

`./compile`

**3.6. Run Hummingbot**

`bin/hummingbot.py`


## Configure Hummingbot for Eterbase
Prerequisite is started hummingbot.

**1. Start configuration**

type command: `config`

**2. Enter password to secure keys**

**3. Choose strategy**

What is your market making strategy? >>> e.g. `pure_market_making`

**4. Import previous configs or create a new config file? (import/create)**

Type `create`.

**4.1. Choose exchange name**

Enter your maker exchange name >>> `eterbase`

**4.2. Select trading pair**

Type e.g. `ETHEUR`

**4.3. Configure strategy**

How to setup market making strategy refer to [Hummingbot configuration manual](https://docs.hummingbot.io/operation/configuration/ "Hummingbot configuration manual").

**4.4. Enter Eterbase API key**

**4.5. Enter Eterbase secret key**

**4.6 Enter Eterbase account of API key**

**4.7 Configure global configuration**

Refer to [Hummingbot configuration manual ](https://docs.hummingbot.io/operation/configuration/ "Hummingbot configuration manual").

**5. Run strategy with given market**

Type: `start`

## Legal

- **License**: Hummingbot is licensed under [Apache 2.0](./LICENSE).
- **Data collection**: read important information regarding [Hummingbot Data Collection](DATA_COLLECTION.md).
