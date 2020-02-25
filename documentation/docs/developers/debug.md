# The Debug Console

The debug console is a powerful tool for Hummingbot developers to inspect and modify the live states in Hummingbot while it's running. It gives access to a live Python console living in the same process as Hummingbot. It can be thought of as similar to the developer console found in most modern browsers.

## Activating the Debug Console

The debug console is disabled by default. You need to enable it by setting `debug_console: true` in `conf/conf_global.yml`.

![Enabling debug console in global config](/assets/img/debug1.png)

## Entering the Debug Console

When you start Hummingbot with debug console enabled, it will print out a "Started debug console" log message at start.

![Started debug console logm essage](/assets/img/debug2.png)

Note the port number printed in the debug message (port 8211 in the example above), you can use `telnet` or `nc` to access the debug console by connecting to the TCP port described in the log message.

![Entering the debug console](/assets/img/debug3.png)

## Accessing Python Modules and Exposed Objects

Once you've entered the debug console, you have access to a fully featured Python interpreter living in the Hummingbot process.

You can access all the exposed properties under the `HummingbotApplication` class via the `hb` object.

Here are some of the exposed properties you can access from the debug console:

- `hb.strategy`: The currently active strategy object
- `hb.markets`: A dictionary of active market connectors
- `hb.acct`: The currently active Ethereum wallet object
- `hb.clock`: The clock object that's driving all the Hummingbot components

![Some exposed variables under 'hb'](/assets/img/debug4.png)

## Sample Ways to Use the Console

Below is an example where a developer queries the currently active bids/asks under the strategy, and the current best ask price on Binance.

![Example](/assets/img/debug5.png)

You should refer to the source code of the exposed objects to see what properties you can inspect and modify inside the debug console.
