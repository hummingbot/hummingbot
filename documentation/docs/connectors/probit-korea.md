# ProBit Korea

ProBit KR Exchange is a Top 20 crypto exchange globally. We have completed over 200 rounds of IEO and have been consistently ranked Top 4 in Korea. ProBit Exchange provides unlimited trading access highlighted by nearly 1,000 trading pairs.

ProBit Exchange's global brand is trusted by millions of users.

- 100,000+ community members
- 800,000+ monthly active users
- 3,000,000 monthly web visitors
- 50,000,000 users on partnering aggregators and wallets such as CoinMarketCap
  The user interface of a Multilingual website supporting 41 different languages
  Marketing and community support in 8 key languages

## Using the connector

To use [ProBit KR](https://www.probit.kr) connector, you will need to generate and provide your API key to trade using Hummingbot.

```
Enter your ProBit KR Client ID >>>
Enter your ProBit KR secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Hummingbot Help Center.

### Creating ProBit API keys

1. Log in to your account [here](https://www.probit.kr/login), then click your My Page > API Management (If you do not have an account, you will have to create one and enable 2FA.)

!!! tip
    You must enable 2FA in your ProBit account to create the API key. [How to enable 2FA](https://support.probit.kr/hc/ko/articles/900003084746-2-%EB%8B%A8%EA%B3%84-%EC%9D%B8%EC%A6%9D-2FA-Google-OTP-%EB%A5%BC-%EC%82%AC%EC%9A%A9%ED%95%98%EB%8A%94-%EB%B0%A9%EB%B2%95-)?

![](/assets/img/probit-korea-account.JPG)

2. Then click the new API key.

![](/assets/img/probit-korea-api.JPG)

!!! note
    To use ProBit Korea, you will need to complete the Korea KYC verification process. Generally, this requires you to be a Korean resident.

3. Now that you have created an API key, connect it to Hummingbot using the `connect` command.

Make sure you store your Secret Key somewhere secure and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.

!!! warning
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous info

### Transaction fees

The default trading fee at ProBit is 0.2%. ProBit's VIP membership structure provides effective trading fees as low as 0% when VIP 6 level and above.

Refer to ProBit's Trading Fee structure [here](https://support.probit.kr/hc/ko/articles/900002984483)

Users can override the default fees by editing [`conf_fee_overrides.yml`](/operation/override-fees/).

### Additional info & support

ProBit Exchange has two platforms, ProBit Global and ProBit Korea. While users are welcome to use either platform, there are certain restrictions when using ProBit Korea. Refer to this [link](https://support.probit.kr/hc/ko/articles/900002984543) for more details.

- [Probit Global](https://www.probit.com)

- [Probit Korea](https://www.probit.kr)

For recent news and any other inquiries, refer to ProBit's support page [here](https://support.probit.kr/hc/ko/categories/900000200306).
