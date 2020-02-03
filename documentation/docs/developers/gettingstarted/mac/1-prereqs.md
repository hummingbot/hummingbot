# Developer Quickstart – macOS | Prerequisites

This section walks you through how to prepare your development environment.

## 1. Install Xcode command line tools

Running Hummingbot on **macOS** requires [Xcode](https://developer.apple.com/xcode/) and Xcode command line tools.

```
xcode-select --install
```

## 2. Install Anaconda3

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

---
# Next: [Installing Hummingbot](/developers/gettingstarted/mac/2-installing)
