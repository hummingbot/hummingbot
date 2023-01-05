// import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace XRPLDEXConfig {
  export interface Config {
    availableNetworks: Array<AvailableNetworks>;
    tradingTypes: Array<string>;
    // markets: MarketsConfig;
    // tickers: TickersConfig;
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
    tradingTypes: ['XRPLDEX_CLOB'],
    // markets: {
    //   url: ConfigManagerV2.getInstance().get(`rippledex.markets.url`),
    //   blacklist: ConfigManagerV2.getInstance().get(
    //     `rippledex.markets.blacklist`
    //   ),
    //   whiteList: ConfigManagerV2.getInstance().get(
    //     `rippledex.markets.whitelist`
    //   ),
    // },
    // tickers: {
    //   source: ConfigManagerV2.getInstance().get(`rippledex.tickers.source`),
    //   url: ConfigManagerV2.getInstance().get(`rippledex.tickers.url`),
    // },
    availableNetworks: [
      {
        chain: 'xrpl',
        networks: ['mainnet', 'testnet'],
      },
    ],
  };
}
