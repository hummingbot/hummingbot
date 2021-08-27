import fs from 'fs';
import yaml from 'js-yaml';
import { Percent } from '@uniswap/sdk';

export namespace ConfigManager {
  export interface Config {
    VERSION: number;
    APPNAME: string;
    PORT: number;
    IP_WHITELIST: string[];
    HUMMINGBOT_INSTANCE_ID: string;
    LOG_PATH: string;
    GMT_OFFSET: number;
    CERT_PATH: string;
    CERT_PASSPHRASE: string;
    ETHEREUM_CHAIN: string;
    INFURA_KEY: string;
    ETH_GAS_STATION_ENABLE: boolean;
    ETH_GAS_STATION_API_KEY: string;
    ETH_GAS_STATION_GAS_LEVEL: string;
    ETH_GAS_STATION_REFRESH_TIME: number;
    ETH_MANUAL_GAS_PRICE: number;
    UNISWAP_ALLOWED_SLIPPAGE: Percent;
    UNISWAP_GAS_LIMIT: number;
    UNISWAP_TTL: number;
    LOG_TO_STDOUT?: boolean;
    UNSAFE_DEV_MODE_WITH_HTTP?: boolean;
  }

  export function validateConfig(o: any): o is Config {
    return (
      'VERSION' in o &&
      'APPNAME' in o &&
      'PORT' in o &&
      'IP_WHITELIST' in o &&
      'HUMMINGBOT_INSTANCE_ID' in o &&
      'LOG_PATH' in o &&
      'GMT_OFFSET' in o &&
      'CERT_PATH' in o &&
      'CERT_PASSPHRASE' in o &&
      'ETHEREUM_CHAIN' in o &&
      'INFURA_KEY' in o &&
      'ETH_GAS_STATION_ENABLE' in o &&
      'ETH_GAS_STATION_API_KEY' in o &&
      'ETH_GAS_STATION_GAS_LEVEL' in o &&
      'ETH_GAS_STATION_REFRESH_TIME' in o &&
      'ETH_MANUAL_GAS_PRICE' in o &&
      'UNISWAP_ALLOWED_SLIPPAGE' in o &&
      'UNISWAP_GAS_LIMIT' in o &&
      'UNISWAP_TTL' in o
    );
  }

  export const configFilePath: string = './conf/gateway-config.yml';
  export let config: Config;
  reloadConfig();

  // after reloading the config, all services should be restarted
  export function reloadConfig(): void {
    let x = yaml.load(fs.readFileSync(configFilePath, 'utf8'));
    if (typeof x === 'object' && validateConfig(x)) {
      config = x;
    } else {
      throw new Error(
        configFilePath + ' does not conform to the expected YAML structure.'
      );
    }

    if (x.VERSION != 1) {
      throw new Error(
        `${configFilePath} has an unexpected version: ${x.VERSION}. Gateway currently only supports version 1.`
      );
    }
  }

  // this allows a client to update the main config file
  export function updateConfig(newConfig: Config) {
    config = newConfig;
    fs.writeFileSync(configFilePath, yaml.dump(config));
  }
}
