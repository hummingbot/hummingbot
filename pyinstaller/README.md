## PyInstaller Builder for macOS and Windows

This directory includes the build files necessary for building ready-to-install packages for Windows and macOS.

## Windows

The `./build` script will automatically generate `Setup.exe` inside the `pyinstaller` directory in Windows. The following software is required for building `Setup.exe` in Windows:

 1. Visual Studio Code, for compiling Hummingbot
 2. Anaconda w/ Python 3.7+
 3. Git Bash, which is installed along with the Windows distribution of Git
 4. NSIS 3, which is the compiler for `Setup.exe`

Once you have the above software installed and working, run the `./build` script in Git Bash and it will automatically generate `Setup.exe` in Windows.


## macOS

The `./build` script will automatically generate `Hummingbot.app` inside the `dist` directory in macOS. No additional software is needed apart from what's normally required for compiling and running Hummingbot in dev mode.