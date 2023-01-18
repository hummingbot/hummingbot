import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace UniswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimitEstimate: number;
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
    gasLimitEstimate: ConfigManagerV2.getInstance().get(
      `uniswap.gasLimitEstimate`
    ),
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
      return type === 'swap' ? ['EVM_AMM'] : ['EVM_AMM_LP'];
    },
    availableNetworks: [
      {
        chain: 'ethereum',
        networks: Object.keys(
          ConfigManagerV2.getInstance().get('uniswap.contractAddresses')
        ).filter((network) =>
          Object.keys(
            ConfigManagerV2.getInstance().get('ethereum.networks')
          ).includes(network)
        ),
      },
      {
        chain: 'polygon',
        networks: Object.keys(
          ConfigManagerV2.getInstance().get('uniswap.contractAddresses')
        ).filter((network) =>
          Object.keys(
            ConfigManagerV2.getInstance().get('polygon.networks')
          ).includes(network)
        ),
      },
    ],
  };
}
