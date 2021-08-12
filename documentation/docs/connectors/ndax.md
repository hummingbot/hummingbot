# NDAX

!!! note
    There is a slight delay in between cancelling and creating new orders when using this connector - this is an expected behavior from the exchange.

[NDAX](https://ndax.io/) (National Digital Asset Exchange) is a Canadian-based centralized exchange which is fully integrated into the Canadian banking system and designed for both individuals and institutions.

They are incorporated in the province of Alberta and registered as a Money Service Business (MSB), making them subject to the Proceeds of Crime (Money Laundering) and Terrorist Financing Act (PCMLTFA) and applicable regulatory framework of the Financial Transactions and Reports and Analysis Centre of Canada (FINTRAC).

## Prerequisites

1. Sign up for an account at https://ndax.io/auth/sign-up
2. User ID (uid)
3. Account username
4. API key
5. API secret key

Your account name and UID can be found in the settings page of your NDAX account.

![](/assets/img/ndax-account-info.png)

## Creating NDAX API keys

1. Log in to your account and go to **Settings** page: https://ndax.io/console/settings
2. In the API Key section, click **Generate New Key**
![](/assets/img/ndax-api-keys-1.png)
3. Select **Allow Trading** permission
4. Click **Generate**
![](/assets/img/ndax-api-keys-2.png)
5. Your secret key will be displayed only once. Copy this key and save it somewhere safe
6. The API key is listed in the API keys section
![](/assets/img/ndax-api-keys-3.png)

## Connecting to NDAX

1. Run the command `connect ndax` in the Hummingbot client's input pane
![](/assets/img/ndax-connect-1.png)
2. Enter the uid, account name, API key and secret key when prompted
3. A message will be displayed when you have successfully connected to the exchange or not. In case of an error, make sure you are entering the correct information
![](/assets/img/ndax-connect-2.png)

## Minimum order sizes

Refer to the table below for the minimum amount when creating orders in NDAX exchange. The minimum size is denominated in base asset.

If your order amount is below the minimum imposed by the exchange, Hummingbot will not create the order. Check your strategy's parameter settings.

| Trading Pair | Minimum |
| ------ | ------- |
| BTCCAD | 0.0001 |
| ETHCAD | 0.0001 |
| XRPCAD | 10 |
| LTCCAD | 0.0001 |
| EOSCAD | 1 |
| XLMCAD | 0.1 |
| DOGECAD | 10 |
| ADACAD | 0.1 |
| USDTCAD | 10 |
| LINKCAD | 0.01 |
| BTCUSDT | 0.0001 |
| DOTCAD | 0.5 |
| UNICAD | 0.1 |
| GRTCAD | 1 |
| COMPCAD | 0.001 |
| AAVECAD | 0.01 |
| MATICCAD | 0.1 |

## Transaction fees

NDAX charges 0.2% fees for buying and selling cryptocurrencies through their exchange.