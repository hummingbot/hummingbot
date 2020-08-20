# MacOS Source Installation

!!! info "Recommended for Developers Only"
    [Installation using Docker](/installation/docker/macOS) is more efficient for running Hummingbot.  Installing from source is only recommended for developers who want to access and modify the software code.

## Part 1. Install Dependencies

Running Hummingbot on **Mac OSX** requires [Xcode](https://developer.apple.com/xcode/) and Xcode command line tools.

#### Step 1. Install Xcode command line tools

```
xcode-select --install
```

#### Step 2. Install Anaconda3

Hummingbot requires Python 3 and other Python libraries. To manage these dependencies, Hummingbot uses Anaconda, an open source environment and package manager for Python that is the current industry standard for data scientists and data engineers.

To install Anaconda, go to [the Anaconda site](https://www.anaconda.com/distribution/) and download the **Python 3.7 installer** for your operating system. Both the [graphical installer](https://docs.anaconda.com/anaconda/install/mac-os/#macos-graphical-install) and the [command line installer](https://docs.anaconda.com/anaconda/install/mac-os/#using-the-command-line-install) will work. Run the installer, and it will guide you through the installation process.

Afterwards, open a Terminal window and try the `conda` command. If the command is valid, then Anaconda has been successfully installed, even if the graphical installer says that it failed.

!!! warning
    If you use ZSH or another Unix shell, copy the code snippet below to your `.zshrc` or similar file. By default, Anaconda only adds it to your `.bash_profile` file. This makes the `conda` command available in your root path.

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

## Part 2. Install Hummingbot

You can install Hummingbot by selecting ***either*** of the following options from the tabs below:

1. **Easy Install**: download and use automated install scripts.
2. **Manual Installation**: run install commands manually.

```bash tab="Option 1: Easy Install"
# 1) Download Hummingbot install script
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-from-source/install-source-macOS.sh -o install-source-macOS.sh

# 2) Enable script permissions
chmod a+x install-source-macOS.sh

# 3) Run installation
./install-source-macOS.sh
```

```bash tab="Option 2: Manual Installation"
# 1) Clone Hummingbot repo
git clone https://github.com/CoinAlpha/hummingbot.git

# 2) Navigate into the hummingbot folder
cd hummingbot

# 3) Run install script
./install

# 4) Activate environment
conda activate hummingbot

# 5) Compile
./compile

# 6) Run Hummingbot
bin/hummingbot.py
```
