# Windows Binary Installation

<iframe width="616" height="347" src="https://www.youtube.com/embed/9TsZ_xjExXs"    frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen>
</iframe>

The Windows setup package is the easiest way for Windows users to setup and run Hummingbot. Windows setup packages are released with every Hummingbot release starting from v0.18.

## Installing Hummingbot with Windows Setup Package

#### Step 1. Download Setup.exe

You can download the Windows installer binary from our [download page](https://hummingbot.io/download).

#### Step 2. Run installer

Once you have downloaded the `Setup.exe` binary package of a Hummingbot release, double click on it to launch the installer.

<img alt="Figure 1: Running the Windows installer" src="/assets/img/windows-setup-1.png" width="499" />

#### Step 3. Start Hummingbot

After completing the setup process, you will be able to find it inside your Windows start menu.

<img alt="Figure 2: Hummingbot installed" src="/assets/img/windows-setup-2.png" width="274" />


## Application Data Files

The application data files (e.g. logs and config files) are located differently for binary package installed Hummingbot vs. source compiled Hummingbot.

For the Windows binary distribution, the application data files are located in `%localappdata%\hummingbot.io\Hummingbot`.