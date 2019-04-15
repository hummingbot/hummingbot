# Coinbase Pro

!!! warning
    The Coinbase Pro connector was recently added to Hummingbot and is still undergoing testing. Please check [Known Issues](/support/tips-issues) before using this connector.

## API keys
In order to trade on <a href="https://pro.coinbase.com" target="_blank">Coinbase Pro</a>, you need an account and need to <a href="https://support.pro.coinbase.com/customer/en/portal/articles/2945320-how-do-i-create-an-api-key-for-coinbase-pro-" target="_blank">create an  API key</a>. 

The API key should have **View** and **Trade** permissions enabled.


## How to create Coinbase Pro API keys?

1 - Log into your Coinbase Pro account, click your avatar and then select **API**.

![coinbase1](/assets/img/coinbase1.png)

!!! tip "Important tip"
    You must enable 2FA in your Coinbase account to create the API key. [How to enable 2FA?](https://support.coinbase.com/customer/en/portal/articles/1658338-how-do-i-set-up-2-factor-authentication-) 

2 - Click on **+ NEW API KEY**. 

![coinbase2](/assets/img/coinbase2.png)

Make sure you give permissions to **View** and **Trade** (**Transfer** is optional), and enter your 2FA code.

![coinbase3](/assets/img/coinbase3.png)

Once you pass the authentication, you’ve created a new API Key!

Your API Secret will be displayed on the screen. Make sure you store your API Secret somewhere secure, and do not share it with anyone.

![coinbase4](/assets/img/coinbase4.png)

When you close the API Secret screen, your API key will be shown in **My API Keys**. The code highlighted in red is your API key. 

![coinbase5](/assets/img/coinbase5.png)

The API Key, Secret, and Passphrase are required for using `hummingbot`. 

!!! tip
    If you lose your API Secret, you can delete the API and create a new one. 
