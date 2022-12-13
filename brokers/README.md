# Integration of hummingbot bots with message brokers

This project extends the hummingbot codebase and implements a thin
layer on-top-of, that enables remote control and monitoring of bots.
The idea is that bots have the ability to connect to local or remote message
brokers and bridges various interfaces in the form of RPCs (Remote Procedure Calls)
and asynchronous events (via PubSub channels). This enables bidirectional
communication between bots and external services.
The goal of this project is to enable remote control and monitoring of Bot
instances towards a plugin-based approach of building HF AMM bots and the
development of bot collaboration schemas in the future.

```
    +-------+                   +-------+
    |       |                   |       |
    | BOT A |                   | BOT B |
    |       |                   |       |
    +---+---+                   +---+---+
        |      +--------------+     |
        |      |              |     |
        |      |              |     |
        +------+  MQTT Broker +-----+
               |              |
            +--+              +-----+
            |  +--------------+     |
            |                       |
     +------+------+       +--------+------+
     |             |       |               |
     | TradingView |       | Orchestration |
     |   Plugin    |       |    Plugin     |
     |             |       |               |
     +-------------+       +---------------+

```

In the context of the current project the MQTT protocol is supported, though
extending to support more protocols, such as AMQP and Redis, was taken into
account. The [commlib](https://github.com/robotics-4-all/commlib-py/tree/v2)
library is used for the implementation of the communication and messaging layer.

The following commands are bridged:

- start
- stop
- import
- config
- balance limit
- history
- status

Below is the list of bridged command interfaces among with their properties:

| ID | URI | Request | Response |
|--------------|-----------|------------|------------| 
| start | `hbot/{botID}/start` | `{"log_level": "str", "restore": bool, "script": str, "is_quickstart": bool}` | `{"status": int, "msg": str}` |
| stop | `hbot/{botID}/stop` | `{"skip_order_cancellation": bool}` | `{"status": int, "msg": str}` |
| import | `hbot/{botID}/import` | `{"strategy": str}` | `{"status": int, "msg": str}` |
| config | `hbot/{botID}/config` | `{"params": List[Tuple[str, Any]]}` | `{"status": int, "msg": str, "changes": List[Dict[str, Any]]}` |
| balance limit | `hbot/{botID}/balance/limit` | `{"exchange": str, "asset": str, "amount": float}` | `{"status": int, "msg": str, "data": str}` |
| balance paper | `hbot/{botID}/balance/paper` | `{"asset": str, "amount": float}` | `{"status": int, "msg": str, "data": str}` |
| history | `hbot/{botID}/history` | `{"days": float, "verbose": bool, "precision": int}` | `{"status": int, "msg": str, "trades": List[Any]}` |
| status | `hbot/{botID}/status` | `{}` | `{"status": int, "msg": str, "data": str}` |

Furthermore, the MQTT bridge, implemented as part of the hummingbot client,
forwards internal Events, Notifications and Logs to the MQTT broker.

Below is the list of bridged publishing interfaces among with their properties:

| ID | URI | Message |
|--------------|-----------|------------|
| Heartbeats | `hbot/{botID}/hb` | `{}` |
| Events | `hbot/{botID}/events` | `{"timestamp": int, "type": str, "data": Dict[str,Any]}` |
| Notifications | `hbot/{botID}/notify` | `{'seq': int, 'timestamp': int, 'msg': str}` |
| Logs | `hbot/{botID}/log` | `{'timestamp': 0.0, 'msg': '', 'level_no': 0, 'level_name': '', 'logger_name': ''}` |

# Usage

The MQTT feature is fully configured via global parameters (`client_config`).

```
mqtt_bridge
∟ mqtt_host              | localhost
∟ mqtt_port              | 1883
∟ mqtt_username          | 
∟ mqtt_password          |
∟ mqtt_ssl               | False
∟ mqtt_logger            | True
∟ mqtt_notifier          | True
∟ mqtt_commands          | True
∟ mqtt_events            | True
∟ mqtt_autostart         | False
```

Use the `mqtt_start` command from the client TUI to initiate MQTT bridge.
Alternatively, you can use the `mqtt_autostart` config parameter to autostart
MQTT connections on startup.


## Use a private broker deployment

Currently, the current implementation supports only the MQTT protocol for 
connecting to message brokers (feature releases will also support AMQP, Redis and Kafka).
Thus a broker with MQTT interfaces is required to connect the bots.
We suggest the following brokers:

- RabbitMQ
- MosquittoMQTT
- EMQX


## Encrypted broker communication (SSL connections)

To enable ssl connections for the hummingbot client Just set the `mqtt_ssl` parameter to `True`.

This feature requires an already deployed message broker with SSL enabled.

For example, to configure EMQX to use SSL encrypted connections follow the instructions 
[here](https://www.emqx.com/en/blog/emqx-server-ssl-tls-secure-connection-configuration-guide).

For local deployments where the message broker and hummingbot bots are hosted on 
a local network or a highly secure private network, it is not mandatory to use SSL, as encryption/description processes
will require a lot of computational resources and may hit system bottlenecks and failures as the number of connections
and data exchange increases (e.g. having several bots and side components deployed).

Though, for scenarios where public message brokers are used (e.g. having a RabbitMQ deployed on AWS and bots executed locally),
it is highly recommended to always use SSL connections to avoid stealing critical data from man-in-the-middle attacks.


## Communicate remotely with your bots via MQTT

MQTT endpoints provided by hummingbot bot instances can be accesses using common mqtt client
libraries.

Though, [commlib\-py](https://github.com/robotics-4-all/commlib-py) Python library 
is recommended as it implements common communication patters such as pure PubSub 
and RPCs, which are used on the bot side. For example, bot commands are implemented 
using the RPC pattern, that is not provided by default for the MQTT protocol.

For test purposes, you can install and use the [commlib-cli](https://github.com/robotics-4-all/commlib-cli) package.
Below are examples of remotely communicating with hummigbot bots via MQTT using 
the `commlib-cli` package.

**Listen to logs:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt sub 'hbot/testbot/log'
```

**Listen to events:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt sub 'hbot/testbot/events'
```

**Listen to notifications:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt sub 'hbot/testbot/notify'
```

**Listen to heartbeats:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt sub 'hbot/testbot/hb'
```

**Execute Start command:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt rpcc 'hbot/testbot/start' '{}'

{'status': 200, 'msg': ''}
```

**Execute Stop command:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt rpcc 'hbot/testbot/stop' '{}'

{'status': 200, 'msg': ''}
```

**Execute Config command / List Config :**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt rpcc 'hbot/testbot/config' '{"params": []}'

{'changes': [], 'status': 200, 'msg': ''}
```

**Execute Config command / Set Single Parameter:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt rpcc 'hbot/testbot/config' '{"params": [["mqtt_bridge.mqtt_autostart", 1]]}'

{'changes': [['mqtt_bridge.mqtt_autostart', 1]], 'status': 200, 'msg': ''}
```


**Execute Config command / Set Multiple Parameters with a single call:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt rpcc 'hbot/testbot/config' '{"params": [["mqtt_bridge.mqtt_autostart", 1], ["mqtt_bridge.mqtt_ssl", 1]]}'

{'changes': [['mqtt_bridge.mqtt_autostart', 1], ['mqtt_bridge.mqtt_ssl', 1]], 'status': 200, 'msg': ''}
```

**Execute Import command:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt rpcc 'hbot/testbot/import' '{"strategy": "conf_liquidity_mining_1"}'

{'status': 200, 'msg': ''}
```

**Execute History command:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt rpcc 'hbot/testbot/history' '{}'

{'status': 200, 'msg': '', 'trades': []}
```

**Execute Balance Limit/Paper commands:**

```bash
commlib-cli --host localhost --port 1883 --btype mqtt rpcc 'hbot/testbot/balance/limit' '{"exchange": "kucoin", "asset": "USDT", "amount": 100}

{'status': 200, 'msg': '', 'data': None}

commlib-cli --host localhost --port 1883 --btype mqtt rpcc 'hbot/testbot/balance/paper' '{"asset": "USDT", "amount": 100}'

{'status': 200, 'msg': '', 'data': None}
```
