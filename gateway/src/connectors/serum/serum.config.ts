import { ConfigManagerV2 } from '../../services/config-manager-v2';
import {AvailableNetworks} from "../../services/config-manager-types";

export namespace SerumConfig {
  export interface Config {
    networkConfig: (network: string) => NetworkConfig;
    availableNetworks: Array<AvailableNetworks>;
    tradingTypes: Array<string>;
    markets: MarketsConfig;
    tickers: TickersConfig;
  }

  export interface NetworkConfig {
    rpcURL: string;
  }

  export interface MarketsConfig {
    url: string;
    blacklist: string[];
    whiteList: string[];
  }

  export interface TickersConfig {
    source: string;
    url: string;
  }

  export const config: Config = {
    networkConfig: (network: string) => {
      return {
        rpcURL: ConfigManagerV2.getInstance().get(`$serum.networks.${network}.rpcURL`),
      }
    },
    tradingTypes: ['exchange'],
    markets: {
      url: ConfigManagerV2.getInstance().get(`$serum.markets.url`),
      blacklist: ConfigManagerV2.getInstance().get(`$serum.markets.blacklist`),
      whiteList: ConfigManagerV2.getInstance().get(`$serum.markets.whitelist`),
    },
    tickers: {
      source: ConfigManagerV2.getInstance().get(`$serum.tickers.source`),
      url: ConfigManagerV2.getInstance().get(`$serum.tickers.url`),
    },
    availableNetworks: [
      { chain: 'solana', networks: ['mainnet-beta', 'devnet'] },
    ],
  };
}