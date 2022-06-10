import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace UniswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimit: number;
    ttl: number;
    maximumHops: number;
    uniswapV3SmartOrderRouterAddress: (network: string) => string;
    uniswapV3NftManagerAddress: (network: string) => string;
    tradingTypes: (type: string) => Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      `uniswap.allowedSlippage`
    ),
    gasLimit: ConfigManagerV2.getInstance().get(`uniswap.gasLimit`),
    ttl: ConfigManagerV2.getInstance().get(`uniswap.ttl`),
    maximumHops: ConfigManagerV2.getInstance().get(`uniswap.maximumHops`),
    uniswapV3SmartOrderRouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `uniswap.contractAddresses.${network}.uniswapV3SmartOrderRouterAddress`
      ),
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
    ],
  };
}
