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

   - **Strategy:**
     - Hummingbot has 9 strategy configurations that can be used for trading or liquidity mining. Hummingbot strategy guide can be found [here](/strategies/).
   - **Strategy_file:**
     - You have the option to save a strategy configuration after every bot creation, allowing you to reuse a strategy quickly with `import`command + **strategy_filename.yml**.

![Top Navigation](/assets/img/top-nav.gif)

1. **Bottom navigation bar**: Displays the information of the following items

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


## Show and hide log pane

The log pane on the right can be shown or hidden in two ways:

1. Click the `log pane` button in the upper right hand corner
2. Press `CTRL + T` shortcut on your keyboard

![Hide Log Pane](/assets/img/hide-log-pane.gif)

## Tabs

Users can now open another tab in the left pane of Hummingbot where the log pane is supposed to be upon entering a command associated with the Tabs feature. Users can now switch between the `log pane` and the new tab they have opened simulateneously.


!!! note
    Currently, the feature only works with the `order_book` parameter.

## Opening and Closing

### Opening a tab

Use the tabs by simply inputting a command associated with the tabs feature.

Upon using the `order_book` command and any suffix it will open a tab automatically.

![opening tabs](/assets/img/tab-opening.png)

![showing tab](/assets/img/leftpane.png)

### Closing a tab

Simply click on the `x` at the top right corner or inputting `parameter_name --close`

One option to close the tab is by clicking on the `x` next to `order_book`

![closing tabs](/assets/img/closing-of-tabs.png)

Alternatively, you can remove the new tab by inputting the `order_book --close` command to close the tab

![alternative closing tabs](/assets/img/name-of-parameter.png)

![closed tabs](/assets/img/closed-tabs.png)


## Keyboard shortcuts

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
| `CTRL + R`        | Reset Style                | Set default color style                            |
| `CTRL + T`        | Toggle logs                | Hide / show the logs pane                    |

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
