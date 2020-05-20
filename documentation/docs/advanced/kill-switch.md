# Kill Switch

Automatically stops the bot when it reaches a certain performance threshold, which can be either positive or negative. This feature uses the same performance calculation methodology as the `history` command.

```
Would you like to enable the kill switch? (Yes/No) >>>
At what profit/loss rate would you like the bot to stop? (e.g. -5 equals 5 percent loss) >>>
```

You can always reconfigure this feature in two ways:

1. Inside Hummingbot run command `config kill_switch_enabled` and/or `config kill_switch_rate`.
1. Editing `conf_global.yml` file using a text editor.