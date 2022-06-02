# Changelog for gateway
All notable changes to gateway should be added to this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.9] - 2021-08-27

### Added

- `/config` returns current config values.

### Changed

- `/` and `/config/update` return JSON responses.

- Added a version number to the config file.

- Cleaned up extraneous options in package.json.

- Make unit tests work and they no longer run the scripts.

## [0.1.8] - 2021-08-18

### Added

- Added uniswap routes:
  - `/` 
  - `/price`
  - `/trade`

## [0.1.7] - 2021-08-16

### Added

- A uniswap service class.

## [0.1.6] - 2021-08-12

### Added

- create an test script that uses all of the ethereum routes. Can be run with `yarn test-scripts`.

## [0.1.5] - 2021-08-11

### Added

- /config/update to update the config file and reload the server

## [0.1.4] - 2021-08-09

### Added

- run gateway with https as default

- hidden option to run in http. This is unsafe and should only be done in development mode.

- manual/curl-with-private-key.sh to test routes while using https

## [0.1.3] - 2021-07-29

### Added

- Added ethereum routes:
  - `/eth`
  - `/eth/balances`
  - `/eth/approve`
  - `/eth/poll`

- Simple express error handler (to be improved in future PRs)

- Add approvedSpenders to Ethereum.

- Add getTokenBySymbol to Ethereum.

- uniswap.config.ts with Uniswap addresses.

- balancer.config.ts with Balancer addresses

## [0.1.2] - 2021-07-27

### Added

- Tests for config-manager.ts.

### Changed

- Drop EthTransactionReceipt, use providers.TransactionReceipt for getTransactionReceipt.

- Trade yaml for js-yaml because it has types.

- Add a Config type to ConfigManager.

- Ethereum extends EthereumBase and has custom behavior for the ethereum gas price.


## [0.1.1] - 2021-07-26

### Added

- Add src/services/gateway-config.ts based on the file from gateway-api, but 
  much simpler and without file watching (the API should be responsible for 
  restarting the service if there is a change to the config file).

- Add src/services/base.ts to hold types and functions common to all services.

### Changed

- Update src/services/ethereum-base.ts to be an implementation using what was in
  src/chains/ethereum/ethereum.ts.

### Removed

- Delete all code in src/chains/ethereum/ethereum.ts since it was moved 
  to ethereum-base.ts. In a future PR this will become a class that inherits
  from EthereumBase.

## [0.1.0] - 2021-07-22

### Added

- Initate a new repo for gateway. This will replace [gateway-api](https://github.com/CoinAlpha/gateway-api) and eventually be added to [hummingbot](https://github.com/CoinAlpha/hummingbot) to form a monorepo.

- Add libraries for TypeScript, eslint, express and uniswap.

- Create dirs and files according to Mike's architecture proposal.

- Create a test dir with a single set of unit tests.

- Create ethereum base class, config and service.
