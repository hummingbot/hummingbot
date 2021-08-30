# Gate.io

Gate.io is operated by Gate Technology Corp. Their mission is to serve the blockchain industry by providing secure and reliable products & services to consumers and companies around the world.

The "Gate ecosystem" consists of Gate.io, Wallet.io, HipoDeFi and Gatechain, all of which were created to provide users with a secure, simple and fair trading platform as well as the ability to safeguard assets and trading information.

## Prerequisites

To use [Gate.io](https://www.gate.io/ref/4566709) connector for spot trading with Hummingbot, you need to create an acount and generate an API key.

### Creating Gate.io API keys

1. Log in to your account [here](https://www.gate.io/login) go to your profile then select **API Management**. If you do not have an account, you will have to create one and verify your ID.

!!! tip
    You must [enable 2FA](https://support.gate.io/hc/en-us/articles/360006647533-Should-I-setup-SMS-or-2FA-for-my-account-) in your Gate io account to create the API key.

![](/assets/img/gateio-api.png)

2. Then click the new API key. Make sure to store & secure the secret key. A secret key will be displayed only once during the API creation.

![](/assets/img/gateio-account.png)

!!! warning
    For API key permissions, we recommend using `trade` and `view` enabled API keys; enabling `transfer,` `or the equivalent is unnecessary `for current Hummingbot strategies.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Connecting to Gate.io

1. Run the command `connect gate_io`
   ![Connecting to Gate io](/assets/img/gateio-connect.gif)
2. Enter the API and secret key generated from your Gate.io account
3. A message will be displayed when you have successfully connected to the exchange

### Minimum order sizes

The minimum order size is about 1 USD in value for all trading pairs.

- [What is minimum order size](https://support.gate.io/hc/en-us/articles/360000808414-What-is-minimum-order-size-)

## Transaction fees

Generally, Gate.io charges 0.2% for both maker and taker orders. However, users who are on a higher VIP Tier can receive discounts. More information can be found in their help center article:

- [Gate.io Trading Fee Overview](https://support.gate.io/hc/en-us/articles/360022907633--Fees-Gate-io-charge-you-)

!!! tip
    If you are on discounted fees, follow the instructions how to [override the default fees](https://docs.hummingbot.io/operation/override-fees/) used in the Hummingbot client.
