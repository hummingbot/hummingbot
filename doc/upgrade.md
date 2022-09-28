# How to upgrade hummingbot from old version

## Get source codes from xdc

```shell
cd ${HUMMINGBOT_PATH}
git remote add xdc https://github.com/Carry-So/hummingbot.git
git fetch xdc
git checkout v1.7.0-xdc
```

## Upgrade hummingbot client

```shell
./clean
./install
conda activate hummingbot
./compile
```

## Upgrade hummingbot gateway

```shell
cd gateway
yarn
yarn build
```

## Clean old conf in gateway

Then remove all configuration files(\*.yml) in directory `gateway/conf` except file `gateway/conf/ssl.yml`. Gateway will recreate these files if not exist when start. Remember backup all files in case of downgrade.

```shell
cd gateway
mkdir conf.bak
mv conf/*.yml conf.bak/
cp conf.bak/ssl.yml conf
```
