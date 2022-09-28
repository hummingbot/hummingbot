# Install hummingbot from XDC

## 1) Environment

-   OS: Ubuntu 22.04
-   hummingbot:
    -   version: v1.7.0-xdc
    -   path: `${HOME}/${HUMMINGBOT_PATH}`

## 2) Install dependencies

Run the following commands in the first terminal:

```shell
sudo apt update -y
sudo apt install -y build-essential curl git httpie jq wget
```

## 3) Install miniconda3

Run the following commands in the first terminal:

```shell
cd ${HOME}
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
chmod +x Miniconda3-latest-Linux-x86_64.sh
./Miniconda3-latest-Linux-x86_64.sh -b -u
./miniconda3/bin/conda init
# Reload .bashrc to register "conda" command
exec bash
conda install -y conda-build
```

## 4) Install hummingbot

Run the following commands in the first terminal:

```shell
cd ${HOME}
export HUMMINGBOT_PATH=${HUMMINGBOT_PATH:-"hummingbot.xdc"}
git clone git@github.com:Carry-So/hummingbot.git ${HUMMINGBOT_PATH}
cd ${HUMMINGBOT_PATH}
git checkout v1.7.0-xdc
./clean
./install
conda activate hummingbot
./compile
```

## 5) Setup hummingbot

### 5.1 Start hummingbot client

Run the command `bin/hummingbot.py` in the first terminal to start hummingbot client. Then set your password according to prompts. Please refer to https://docs.hummingbot.org/operation/password/ if has problem.

### 5.2 Generate certs

Run the command `gateway generate-certs` in the input pane(lower left) of hummingbot client. You will be prompted to enter the passphrase used to encrypt these certs. We recommend using the same password in last step. **Do not quit hummingbot client now!.**

```text
>>> gateway generate-certs
Enter pass phase to generate Gateway SSL certifications >>> *****
Gateway SSL certification files are created in /home/<YOUR NAME>/.hummingbot-gateway/hummingbot-gateway-********/certs
```

Take note of this folder path. Please refer to: https://docs.hummingbot.org/developers/gateway/setup/#1-generate-certs if has problem.

### 5.3 Setup gateway ssl

Run the following commands to setup gateway ssl in the second terminal:

```shell
export HUMMINGBOT_PATH=${HUMMINGBOT_PATH:-"hummingbot.xdc"}
cd ${HOME}/${HUMMINGBOT_PATH}/gateway
setup/generate_conf.sh conf

CERT=$(ls -Frt ${HOME}/.hummingbot-gateway | grep -E '^hummingbot-gateway-[0-9a-z]{8}/$' | tail -n 1)
export CERTS_PATH="${HOME}/.hummingbot-gateway/${CERT:0:-1}/certs"
echo "CERTS_PATH=${CERTS_PATH}"

cat > conf/ssl.yml <<EOF
caCertificatePath: ${CERTS_PATH}/ca_cert.pem
certificatePath: ${CERTS_PATH}/server_cert.pem
keyPath: ${CERTS_PATH}/server_key.pem

EOF

cat conf/ssl.yml
```

Please refer to: https://docs.hummingbot.org/developers/gateway/setup/#2-set-up-gateway-ssl if has problem.

### 5.4 Start hummingbot gateway

Run the following commands to start hummingbot gateway in second terminal:

```shell
# Install dependencies
yarn

# Compile code
yarn build

# Start server using certs passphrase, such as: `yarn start --passphrase=daniel`
yarn start --passphrase=<PASSWORD>
```

Please refer to: https://docs.hummingbot.org/developers/gateway/setup/#3-run-gateway-server if has problem.

### 5.5 Connect wallet

The hummingbot client should show: `Gateway: ONLINE` on the top of log pane(right) now. Run the following commands in Hummingbot to test the connection and connect to a DEX like Uniswap. Notice: the private key has no `0x` prefix(length is 64 characters) in this step!

```text
>>> gateway test-connection

Successfully pinged Gateway.

>>> gateway connect uniswap

What chain do you want uniswap to connect to? (ethereum, polygon) >>> ethereum

Which network do you want uniswap to connect to? (mainnet, kovan, ropsten, arbitrum_one, optimism) >>> mainnet

Do you want to continue to use `https://rpc.ankr.com/eth` for ethereum-mainnet? (Yes/No) >>> Yes

Enter your ethereum-mainnet wallet private key >>> *******************************
The uniswap connector now uses wallet [public address] on ethereum-mainnet.
```

Now, you can type command `exit` in hummingbot client to quit now. When you exit and restart Hummingbot, it should automatically detect whether Gateway is running and connect to it. Please refer to: https://docs.hummingbot.org/developers/gateway/setup/#4-connect-wallet if has problem.
