# Running Bots in the Cloud

!!! note
    The commands below assume that you are already inside the Hummingbot CLI on a remote server. Please see [Installation](/installation) and [Client](/operation/client) if you need help to install and launch the CLI.

## Running bots in the background

Credits to discord user `@matha` for this question and `@pfj` for the solution.

To run an instance in the background on the cloud, run either of the following commands: `screen` or `screen -S $NAME`. Use the latter to be more explicit if you want to run multiple bots.

Then start the bot like normal. To exit the screen, press `Ctrl-A-D`. 

To log back into the screen, either use `screen` or `screen -r $NAME` to open a specific instance of your screen. To list all running instances, use `screen -ls`.

We recommend that users download separate docker images for each client that they wish to run.
