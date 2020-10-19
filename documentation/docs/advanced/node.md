# Using Ethereum Nodes

You need an Ethereum node for strategies that trade on Ethereum-based decentralized exchanges, such as Radar Relay, Bamboo Relay, and Dolomite.

Run command `config ethereum_rpc_url` to use your Ethereum node with Hummingbot.

```
Which Ethereum node would you like your client to connect to? >>>
```

Below, we list different ways that you can access an Ethereum node.

## Option 1. Hosted Node

### a. Infura

[Infura](https://infura.io/) provides free and the most widely used Ethereum nodes.

1. Sign up for an account on infura.io
![](/assets/img/infura1.png)
2. Click on **Ethereum** and **Create a project**.
![](/assets/img/infura2.png)
3. Name your project and click **Create**.
4. In **Keys** section and under **Endpoints** you'll find your Ethereum node as shown in the highlighted area.
![](/assets/img/infura3.png)
5. The websocket address is below the Ethereum node that starts with `wss://`

### b. QuikNode

[QuikNode](https://www.quiknode.io/) is a popular and high-performance node service.

1. Sign up for an account on QuikNode.io
![](/assets/img/QuikNode1.png)
2. Click on **CREATE NODE** after verifying your e-mail address.
![](/assets/img/QuikNode2.png)
3. Select **LAUNCH** plan as it'll give you free trial (you can upgrade later according to your needs), then choose **ETH** as chain, select **Mainnet** as network, click on **CONTINUE TO BILLING** and complete the billing process.
![](/assets/img/QuikNode3.png)
4. Under the **Nodes** section you'll find your new node, click on the node and open the node dashboard.
5. In **Get Started** option from left-vertical menu you can find websocket address under **WSS Provider** starting with `wss://`, you can simply copy and use it.

### c. Alchemy

[Alchemy](https://alchemyapi.io/) Supernode is the most widely used Ethereum API.

1. Sign up for an account on Alchemyapi.io after clicking on **Get started for free**.
![](/assets/img/Alchemy1.png)
2. Enter your Team name and App name then select **Mainnet** and click on **Create App**.
![](/assets/img/Alchemy2.png)
3. Select the plan according to your need and complete the billing process.
4. Now you'll see the dashboard of your app.
![](/assets/img/Alchemy3.png)
5. The websocket address starting with `wss://` is below the http address in the **Update Configuration** section.

## Option 2. Run your own local node

The most decentralized way to access an Ethereum node is to run your own node!

Running your own node may require dedicated storage and compute, as well as some technical skills. These are the two most widely used Ethereum clients:

- [Geth (go-ethereum)](https://github.com/ethereum/go-ethereum/wiki/Building-Ethereum)
- [Parity](https://github.com/paritytech/parity-ethereum)

!!! note
    These may require several hours to days to sync and may require some troubleshooting when first running.

## Option 3. Dedicated blockchain hardware
Get dedicated hardware for your Ethereum node.  Ethereum nodes are meant to run constantly 24/7 and use up a material amount of computational resources (CPU, RAM, and storage).  For more serious users, it may make sense to use dedicated hardware.

### Software
- [DAppNode](https://dappnode.io/) is software that automates the installation and operation of Ethereum (as well as other blockchains) on dedicated hardware.it easier to start and operate an Ethereum node and can run other blockchains.

### Hardware
- [IntelⓇ NUC mini PC](https://www.intel.com/content/www/us/en/products/boards-kits/nuc.html): DIY, customize and configure your own hardware.
- [Avado](https://ava.do/): purpose built hardware that is pre-loaded with DAppNode.
