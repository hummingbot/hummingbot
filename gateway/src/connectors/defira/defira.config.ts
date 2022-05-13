import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace DefiraConfig {
  export interface NetworkConfig {
    allowedSlippage: (version: number) => string;
    gasLimit: (version: number) => number;
    ttl: (version: number) => number;
    uniswapV2RouterAddress: (network: string) => string;
    // TODO: probably will not need this
    uniswapV3RouterAddress: (network: string) => string;
    // TODO: probably will not need this
    uniswapV3NftManagerAddress: (network: string) => string;
    tradingTypes: (network: string) => Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: (version: number) =>
      ConfigManagerV2.getInstance().get(
        `defira.versions.v${version}.allowedSlippage`
      ),
    gasLimit: (version: number) =>
      ConfigManagerV2.getInstance().get(`defira.versions.v${version}.gasLimit`),
    ttl: (version: number) =>
      ConfigManagerV2.getInstance().get(`defira.versions.v${version}.ttl`),
    uniswapV2RouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `defira.contractAddresses.${network}.uniswapV2RouterAddress`
      ),

    // TODO: probably will not need this
    uniswapV3RouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `defira.contractAddresses.${network}.uniswapV3RouterAddress`
      ),
    // TODO: probably will not need this
    uniswapV3NftManagerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `defira.contractAddresses.${network}.uniswapV3NftManagerAddress`
      ),
    tradingTypes: (network: string) =>
      network === 'v2' ? ['EVM_AMM'] : ['EVM_Range_AMM'],
    availableNetworks: [
      {
        chain: 'ethereum',
        networks: Object.keys(
          ConfigManagerV2.getInstance().get('defira.contractAddresses')
        ),
      },
    ],
  };
}
