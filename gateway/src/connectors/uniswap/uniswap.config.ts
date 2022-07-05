import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace UniswapConfig {
  export interface NetworkConfig {
    maximumHops: number;
    allowedSlippage: (version: number) => string;
    gasLimit: number;
    ttl: (version: number) => number;
    uniswapV3SmartOrderRouterAddress: (network: string) => string;
    uniswapV3NftManagerAddress: (network: string) => string;
    tradingTypes: (type: string) => Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: (version: number) =>
      ConfigManagerV2.getInstance().get(
        `uniswap.versions.v${version}.allowedSlippage`
      ),
    gasLimit: ConfigManagerV2.getInstance().get(`uniswap.gasLimit`),
    maximumHops: ConfigManagerV2.getInstance().get(`uniswap.maximumHops`),
    uniswapV3SmartOrderRouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `uniswap.contractAddresses.${network}.uniswapV3SmartOrderRouterAddress`
      ),
    ttl: (version: number) =>
      ConfigManagerV2.getInstance().get(`uniswap.versions.v${version}.ttl`),
    uniswapV3NftManagerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `uniswap.contractAddresses.${network}.uniswapV3NftManagerAddress`
      ),
    tradingTypes: (type: string) => {
      return type === 'swap' ? ['EVM_AMM'] : ['EVM_Range_AMM'];
    },
    availableNetworks: [
      {
        chain: 'ethereum',
        networks: Object.keys(
          ConfigManagerV2.getInstance().get('uniswap.contractAddresses')
        ),
      },
      {
        chain: 'polygon',
        networks: Object.keys(
          ConfigManagerV2.getInstance().get('uniswap.contractAddresses')
        ),
      },
    ],
  };
}
