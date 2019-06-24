# MacOS Source Installation

## Dependencies

Running `hummingbot` on **Mac OSX** requires [Xcode](https://developer.apple.com/xcode/) and Xcode command line tools.

### 1. Install Xcode command line tools

```
xcode-select --install
```

### 2. Install Anaconda3

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
