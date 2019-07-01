# Running Bots in the Cloud

!!! tip
    Read our blog about running [Hummingbot on different cloud providers](https://www.hummingbot.io/blog/2019-06-cloud-providers/).

## Running bots in the background

**Prevent cloud instance from going to sleep**

To run an instance in the background on the cloud, run either of the following commands: `screen` or `screen -S $NAME`. Use the latter to be more explicit if you want to run multiple bots.

Then start the bot like normal. To exit the screen, press `Ctrl-A-D`. 

To log back into the screen, either use `screen` or `screen -r $NAME` to open a specific instance of your screen. To list all running instances, use `screen -ls`.

We recommend that users download separate docker images for each client that they wish to run.

<small>Credits to discord user `@matha` for this question and `@pfj` for the solution.</small>

## Access your cloud instance from your phone

Use Hummingbot's [Telegram integration](/operation/telegram) to connect to your cloud instance without a computer.
