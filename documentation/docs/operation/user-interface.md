# User Interface Guide

![Hummingbot CLI](/assets/img/userinterface-hummingbot.gif)

The CLI is divided into five panes:

1. **Input pane (lower left)**: Where users enter commands

![Hummingbot CLI](/assets/img/input-pane.gif)

2. **Output pane (upper left)**: Prints the output of the user's commands

![Hummingbot CLI](/assets/img/output-pane.gif)

3. **Log pane (right)**: Log messages

![Log Pane](/assets/img/log-messages.gif)

4. **Top navigation bar**: Displays the status/information of the following items

   - **Version:**

     - Reference of Version Release (Currently at 0.39)

   - **paper_trade_mode:**

     - A Hummingbot feature that allows users to simulate trading strategies without risking any assets. Learn more about [Paper Trade Mode](/features/paper-trade)

   - **Strategy:**
     - Hummingbot has 9 strategy configurations that can be used for trading or liquidity mining. Hummingbot strategy guide can be found [here](/strategies/overview/).
   - **Strategy_file:**
     - You have the option to save a strategy configuration after every bot creation, allowing you to reuse a strategy quickly with `import`command + **strategy_filename.yml**.

![Top Navigation](/assets/img/top-nav.gif)

5. **Bottom navigation bar**: Displays the information of the following items

   - Trades
     - Number of trades done by the bot
   - Total P&L
     - Total profit & loss
   - Return%
     - Return percentage of assets
   - CPU
     - CPU usage of the computer
   - Mem

     - Memory usage of the computer

   - Threads

   - Duration
     - Duration of the trading session

![Bottom Navigation](/assets/img/bottom-nav.gif)

# Keyboard shortcuts

| Keyboard Combo    | Command                    | Description                                  |
| ----------------- | -------------------------- | -------------------------------------------- |
| `Double CTRL + C` | Exit                       | Press `CTRL + C` twice to exit the bot       |
| `CTRL + S`        | Status                     | Show bot status                              |
| `CTRL + F`        | Search / <br/> Hide Search | Toggle search in log pane                    |
| `CTRL + X`        | Exit Config                | Exit from the current configuration question |
| `CTRL + A`        | Select All                 | \* Select all text                           |
| `CTRL + Z`        | Undo                       | \* Undo action                               |
| `Single CTRL + C` | Copy                       | \* Copy text                                 |
| `CTRL + V`        | Paste                      | \* Paste text                                |

_\* Used for text edit in input pane only._

**Note about search:**

1. Press `CTRL + F` to trigger display the search field

2. Enter your search keyword (not case sensitive)

3. Hit `Enter` to jump to the next matching keyword (incremental search)

4. When you are done, press `CTRL + F` again to go back to reset

### Linux

| Keyboard Combo                   | Command |
| -------------------------------- | ------- |
| CTRL + C                         | Copy    |
| SHIFT + RMB (right-mouse button) | Paste   |

To highlight, hold `SHIFT + LMB` (left mouse button) and drag across the text you want to select.

### macOS

| Keyboard Combo | Command |
| -------------- | ------- |
| ⌘ + C          | Copy    |
| ⌘ + V          | Paste   |

!!! note
    To select text on macOS, you may need to enable the **Allow Mouse Reporting** option by pressing `⌘ + R` or selecting **View > Allow Mouse Reporting** in the menu bar.

![allowmouse](/assets/img/allow_mouse_reporting.png)

Then you should be able to select text by holding `LMB` (left mouse button) and drag. You can also hold down `⌥ + shift` to select specific lines like the image below.

![highlightmacos](/assets/img/highlight_macos.png)

When accessing Hummingbot on a Linux cloud server through `ssh` using a macOS terminal, hold down the `Option ⌥` key or `⌥ + ⌘` to highlight text.

### Windows

| Keyboard Combo   | Command |
| ---------------- | ------- |
| CTRL + SHIFT + C | Copy    |
| CTRL + SHIFT + V | Paste   |

To use this shortcut, check this box by doing a right-click on the title bar at the top of the Hummingbot window, then select **Properties**.

![](/assets/img/properties_windows.png)
