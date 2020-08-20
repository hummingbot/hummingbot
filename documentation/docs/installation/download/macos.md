# macOS Binary Installation

<iframe width="616" height="347" src="https://www.youtube.com/embed/klN-ToclwW4" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen>
</iframe>

The macOS install package allows very easy installation and running Hummingbot on Mac computers. macOS install packages are released with every Hummingbot release starting from v0.18.

## Installing Hummingbot with macOS Install Package

#### Step 1. Download Hummingbot .dmg file

You can download the macOS .dmg file from our [download page](https://hummingbot.io/download).

#### Step 2. Drag application bundle to /Applications folder

Open the downloaded .dmg file, drag and drop the application bundle into the `/Application` folder.

<img alt="Figure 1: Drag and Drop Application Bundle" src="/assets/img/macos-dmg-1.png" width="374" />

#### Step 3. Start Hummingbot

Launch Hummingbot just like any other installed application on your Mac. You can also add it to your Dock for easy access.

<img alt="Figure 2: Added Hummingbot to Dock" src="/assets/img/macos-dmg-2.png" width="182" />

When you're starting Hummingbot for the first time, it will ask for permission to launch Terminal, since it is a Terminal application. Press "OK" to allow it to open.

<img alt="Figure 3: Granting Terminal access to Hummingbot" src="/assets/img/macos-dmg-3.png" width="532" />

## Application Data Files

The application data files (e.g. logs and config files) are located differently for binary package installed Hummingbot vs. source compiled Hummingbot.

For the macOS .dmg distribution, the application data files are located in `~/Library/Application\ Support/Hummingbot`