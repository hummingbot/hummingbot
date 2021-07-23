# Windows Source Installation

Installing from source is only recommended for developers who want to access and modify the software code. We recommend that Windows users either:

- Follow the guide on [Hummingbot Windows Binary version](/installation/download/windows/) using `setup.exe` installer binary.

- Follow the guide on [Hummingbot Windows Docker version](/installation/docker/windows). Note that it is recommended to use the Docker Toolbox over native Docker in most cases.


## Installing Hummingbot on Windows System

#### Step 1. Install required Applications
1. Install [Git for Windows](https://git-scm.com/download/win).
2. Install [Python for Windows](https://www.python.org/downloads/windows/).
3. Install [Anaconda or miniconda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/windows.html).
4. Install [Visual Studio Code](https://code.visualstudio.com/download), [Visual Studio BuildTools 2019, Core Features, C++](https://visualstudio.microsoft.com/thank-you-downloading-visual-studio/?sku=BuildTools&rel=16) and [C++ redistributable 2019](https://aka.ms/vs/16/release/VC_redist.x64.exe).

!!! note
    - During installation make sure to add Anaconda or Miniconda to your PATH environmental variable by clicking the tick box as shown below, or you can add them [manually](https://www.geeksforgeeks.org/how-to-setup-anaconda-path-to-environment-variable/).
    ![anaconda-path](/assets/img/anaconda-path.png)
    - Some prerequisites are large applications and may need to restart your computer.

#### Step 2. Install Hummingbot on Windows System

Launch Git Bash App<br />
![git-bash](/assets/img/git-bash.png)

```
# initialized conda
conda init bash
# exit git-bash to take effect
exit
# launch Git Bash App again
```

You can install Hummingbot by selecting ***either*** of the following options from the tabs below:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.

```bash tab="Option 1: Easy Install"
# 1) Navigate to root folder
cd ~

# 2) Download install script
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-windows.sh -o install-source-windows.sh

# 3) Enable script permissions
chmod a+x install-source-windows.sh

# 4) Run installation
./install-source-windows.sh
```

```bash tab="Option 2: Manual Installation"
cd ~
export CONDAPATH="$(pwd)/miniconda3"
export PYTHON="$(pwd)/miniconda3/envs/hummingbot/python3"
# Clone Hummingbot
git clone https://github.com/CoinAlpha/hummingbot.git
# Install Hummingbot
export hummingbotPath="$(pwd)/hummingbot" && cd $hummingbotPath && ./install
# Activate environment and compile code
conda activate hummingbot && ./compile
# Start Hummingbot
winpty python bin/hummingbot.py
```

