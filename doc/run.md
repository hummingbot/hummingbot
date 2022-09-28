# Run hummingbot after setup

Pelase read https://docs.hummingbot.org/ for other operations.

## 1) Environment

- OS: Ubuntu 22.04
- hummingbot:
  - version: v1.7.0-xdc
  - path: `${HOME}/${HUMMINGBOT_PATH}`

## 2) Start hummingbot gateway

Run the following commands to start hummingbot gateway in the first terminal:

```shell
export HUMMINGBOT_PATH=${HUMMINGBOT_PATH:-"hummingbot.xdc"}
cd ${HOME}/${HUMMINGBOT_PATH}/gateway

# Start server using certs passphrase, such as: `yarn start --passphrase=daniel`
yarn start --passphrase=<PASSWORD>
```

## 3) Start hummingbot client

Run the following commands in the second terminal:

```shell
export HUMMINGBOT_PATH=${HUMMINGBOT_PATH:-"hummingbot.xdc"}
cd ${HOME}/${HUMMINGBOT_PATH}
conda activate hummingbot
bin/hummingbot.py
```
