# Install from source

## OS-specific dependencies

We provide users with binaries compiled for each operating systems. Below, we list OS-specific dependencies and suggestions.

OS | Notes
---|---
**Mac OSX** | You may need to install [Xcode](https://developer.apple.com/xcode/) or Xcode command line tools.
**Linux** | We recommend Ubuntu 18.04, though Hummingbot should work on other version of Linux as well. If you are installing Hummingbot on a fresh Linux virtual machine, we recommend installing the `build-essential` package beforehand, since Hummingbot uses the `gcc` compiler and other libraries it contains: <br/><br/> ```sudo apt-get update```<br/>```sudo apt-get install build-essential```
**Windows** | Hummingbot is designed and optimized for macOS and Linux. While a Windows binary is available, it is not actively supported. Instead, we recommend that Windows users install <a href="https://docs.microsoft.com/en-us/windows/wsl/faq" target="_blank">Windows Subsystem for Linux</a>, which allows you to run the Linux version.

## 1. Install Anaconda

Hummingbot requires Python 3 and other Python libraries. To manage these dependencies, Hummingbot uses Anaconda, an open source environment and package manager for Python that is the current industry standard for data scientists and data engineers.

To install Anaconda, go to [the Anaconda site](https://www.anaconda.com/distribution/) and download the **Python 3.7 installer** for your operating system. Both the graphical installer and the command line installer will work. Run the installer, and it will guide you through the installation process.

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

## 2. Download the Hummingbot client

Clone or download the [Github repository](https://github.com/coinalpha/hummingbot).

## 3. Run install script

In a Terminal or bash window, go to the root directory:

```
cd hummingbot
```

Run the install script, which creates a custom Anaconda environment and installs the Python libraries and other dependencies needed by the bot:

```
./install
```

## 4. Activate environment

The installation script creates a custom Anaconda environment that manages dependencies used by Hummingbot. Activate the environment:

```
conda activate hummingbot
```
The environment has been activated when you see a `(hummingbot)` prefix before your Terminal command prompt:

!!! note
    Make sure you are on latest conda version. You can check by typing `conda --version`. In addition, you might have
    to type `conda init bash` if you see a message saying that your shell is not configured to use `conda activate`.

!!! note
    Ensure that you have activated the `hummingbot` environment before **compiling** or **running the bot**.

## 5. Compile

Compile and Cythonize the source code into the executable binary:

```
./compile
```

## 6. Run Hummingbot

Start Hummingbot by entering:
```
bin/hummingbot.py
```
