import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace UniswapConfig {
  export interface NetworkConfig {
    maximumHops: number;
    allowedSlippage: (version: number) => string;
    ttl: (version: number) => number;
    uniswapV3SmartOrderRouterAddress: (network: string) => string;
    uniswapV3NftManagerAddress: (network: string) => string;
    tradingTypes: (network: string) => Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: (version: number) =>
      ConfigManagerV2.getInstance().get(
        `uniswap.versions.v${version}.allowedSlippage`
      ),
    gasLimit: ConfigManagerV2.getInstance().get(`uniswap.gasLimit`),
    ttl: ConfigManagerV2.getInstance().get(`uniswap.ttl`),
    maximumHops: ConfigManagerV2.getInstance().get(`uniswap.maximumHops`),
    uniswapV3SmartOrderRouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `uniswap.contractAddresses.${network}.uniswapV3SmartOrderRouterAddress`
      ),
    ttl: (version: number) =>
      ConfigManagerV2.getInstance().get(`uniswap.versions.v${version}.ttl`),
    uniswapV2RouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `uniswap.contractAddresses.${network}.uniswapV2RouterAddress`
      ),
    uniswapV3RouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `uniswap.contractAddresses.${network}.uniswapV3RouterAddress`
      ),
    uniswapV3NftManagerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `uniswap.contractAddresses.${network}.uniswapV3NftManagerAddress`
      ),
    tradingTypes: (network: string) =>
      network === 'v2' ? ['EVM_AMM'] : ['EVM_Range_AMM'],
    availableNetworks: [
      {
        chain: 'ethereum',
        networks: Object.keys(
          ConfigManagerV2.getInstance().get('uniswap.contractAddresses')
        ),
      },
    ],
  };
}
