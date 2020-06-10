# Asset Restriction

**Updated as of `v0.28.0`**

This feature allows you to restrict the amounts of certain assets that Hummingbot is allowed to use on exchanges. You can specify the amount of each currency/asset that the bot can trade. This enables you to secure your assets and avoid unexpected losses.

## How It Works
### Enabling and Disabling

Type `config asset_restriction_enabled` to enable/disable this setting. Answer `Yes` to the prompt if you would like to enable asset restrictions, and `No` to disable the feature. 

Whenever `asset_restriction_enabled` is set to True, the bot is limited to using the amount of assets specified in the configurations ([see below](./#configuring-asset-restrictions)).

By default this feature is disabled and `asset_restriction_enabled` is set to `False`.

### Configuring Asset Restrictions

When `asset_restriction_enabled` is set to True, you will be prompted to configure `asset_restriction` to set the restricted assets. 

To configure directly, type `configure asset_restriction`.

Your response should be formatted as a list of pairs of asset keys and the amount you want Hummingbot to have access to: `[["Asset-1", 100], ... ]`. Note that assets not in the list will be considered fully restricted and Hummingbot will not be able to trade those assets.

Note that this parameter is empty by default. Thus, all assets are restricted by default.

**Sample Response**:
```json
asset_restriction_enabled: Yes
asset_restriction: [["BTC", 1], ["USDT", 20]]
```

**Sample Configuration**:
![](/assets/img/asset-restriction-config.png)

## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **asset_restriction_enabled** | `Would you like to restrict the assets Hummingbot can access?` | When enabled, Hummingbot is only able to access a certain amount of the specified assets. |
| **asset_restriction** | `Enter asset restriction settings (Input must be a valid json)` | For each asset, Hummingbot will only be allowed to use the amount specified in this list. |