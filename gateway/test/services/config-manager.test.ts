import fs from 'fs';
// import { safeJsonParse, ParseResult } from '../../src/services/base';
import { ConfigManager } from '../../src/services/config-manager';
import 'jest-extended';
import yaml from 'js-yaml';

test('validateConfig', () => {
  expect(
    ConfigManager.validateConfig(
      yaml.load(fs.readFileSync(ConfigManager.configFilePath, 'utf8'))
    )
  ).toEqual(true);
});

test('test default config from the repo', () => {
  expect(ConfigManager.config.APPNAME).toEqual('Hummingbot Gateway API');
  expect(ConfigManager.config.PORT).toEqual(5000);
  expect(ConfigManager.config.IP_WHITELIST).toEqual([]);
  expect(ConfigManager.config.HUMMINGBOT_INSTANCE_ID).toEqual(
    '67618e88c8b8f52342e61c6e46dc2571fa48543b'
  );
  expect(ConfigManager.config.LOG_PATH).toEqual('./logs');
  expect(ConfigManager.config.GMT_OFFSET).toEqual(800);
  expect(ConfigManager.config.CERT_PATH).toEqual('');
  expect(ConfigManager.config.CERT_PASSPHRASE).toEqual('');
  expect(ConfigManager.config.ETHEREUM_CHAIN).toEqual('mainnet');
  expect(ConfigManager.config.INFURA_KEY).toEqual('');
  expect(ConfigManager.config.ETH_GAS_STATION_ENABLE).toEqual(true);
  expect(ConfigManager.config.ETH_GAS_STATION_API_KEY).toEqual('');
  expect(ConfigManager.config.ETH_GAS_STATION_GAS_LEVEL).toEqual('fast');
  expect(ConfigManager.config.ETH_GAS_STATION_REFRESH_TIME).toEqual(60);
  expect(ConfigManager.config.ETH_MANUAL_GAS_PRICE).toEqual(100);
});
