![Hummingbot](https://i.ibb.co/X5zNkKw/blacklogo-with-text.png)
# Hummingbot Gateway
----

Hummingbot Gateway is middleware that connects to various blockchains and the decentralized exchanges (DEX) on each chain. Gateway connects to each protocol and DEX's smart contract interface and/or wraps its Javascript-basked SDK, in order to expose standardized REST API endpoints for each protocol (wallet, node & chain interaction) and DEX (pricing, trading & liquidity provision). 

Gateway may be used alongside the main Hummingbot client to enable trading on DEXs, or as a standalone module by external developers.

>Note: After Hummingbot version 0.X, the Gateway code was moved into the main Hummingbot repository in order ensure future cross-compatibility with each Hummingbot release. Prior to this version, the Gateway codebase was maintained in its own Github repository (https://github.com/coinalpha/gateway-api), which is not compatible with version 0.X and after.

## Connectors

## Configuration

You can either use the Hummingbot client to create a config file or you can create or edit one manually. Copy the sample Gateway config file [global_conf.yml.example](./conf/global_conf.yml.example) to `global_conf.yml` in the same directory. Then, edit the file with your settings.

## Install and run locally

This is a TypeScript project and has a build phase. You can use `npm` or `yarn` to download dependencies, build then run it.

```bash
yarn
yarn build
yarn start
```

## Testing

Test using some of the commands in the [test script](./manual_tests/curl.sh). You will need to store your private key in an environment variable `ETH_PRIVATE_KEY`.

## Linting

This repo uses `eslint` and `prettier`. When you run `git commit` it will trigger the `pre-commit` hook.
This will run `eslint` on the `src` and `test` directories.

You can lint before committing with:

```bash
yarn run lint
```

You can run the prettifier before committing with:

```bash
yarn run prettier
```
