---
title: "Miscellaneous"
description: Other related info on developing connectors
---

import Callout from "../../src/components/Callout";

## Adding Connectors to Exchanges on Other Blockchains

Hummingbot currently has connectors to Ethereum-based exchanges and has built-in [Ethereum wallet support](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/wallet/ethereum).

We plan to support multiple blockchains in the near future. To support blockchains other than Ethereum, connectors for new blockchains other than Ethereum would require integrations that enable the following blockchain-specific functionalities:

- interactions with blockchain wallets: import, creation, encryption
- interactions with blockchain nodes
- interactions with event watchers: balances, token address mappings, contract events, token events,
- interaction with blockchain-based exchanges

For more information, please contact our engineering team at dev@coinalpha.com.

## Maintaining API Limits Using Throttle Class

The throttle functionality in the Hummingbot utils directory can be used to control the order and rate at which requests are made to the endpoint of a particular connector. For instance, it can be used to send a request to endpoints according to the set weight (or priority) at specific intervals. It is advised that this functionality is employed in connectors to prevent situations whereby API keys or IP gets blocked due to exceeding the limits by exchanges.

### How the throttle function works

The following code is used to explain how the throttle function works. The code is included in [`hummingbot/core/utils/asyncio_throttle.py`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/utils/asyncio_throttle.py) file and can also be executed by using the Python interpreter.

```
throttler = Throttler(rate_limit=(20, 1.0))

async def task(task_id, weight):
	async with throttler.weighted_task(weight):
		print(int(time.time()), f"Cat {task_id}: Meow {weight}")

async def test_main():
	tasks = [
		task(1, 5), task(2, 15), task(3, 1), task(4, 10), task(5, 5), task(6, 5)
	]
	await asyncio.gather(*tasks)

loop = asyncio.get_event_loop()
loop.run_until_complete(test_main())
```

In the code above, the `Throttler` class will be initiated with a `rate_limit` of 20 weight per second.

Then the `task` method is then defined to be the entry point for the tasks. It also prints tasks in the order in which they are executed.

Lastly, a list of tasks is created and queued.

Upon running the code, the printed output summarized that all tasks were executed in 3 seconds. Tasks 1, 3, and 4 with cumulative weights of 16 were first executed in the first second. Then Task 2 with weight 15 was completed in the next second. And tasks 5 and 6 with a cumulative weight of 10 were executed last.

<Callout
  type="note"
  body="
#(1)# The maximum weight assigned to any task must be one less than the weight set in the rate_limit to avoid a situation whereby such a task would never get executed. i.e, with `rate_limit(15, 1)`, the max weight any task of that instance should have should be 14.
#(2)# The most important tasks should have a lower weight than less important tasks."
/>

As of this writing, the Binance connector uses the throttler functionality and can be used as a guide for implementing the throttler functionality for new connectors.
