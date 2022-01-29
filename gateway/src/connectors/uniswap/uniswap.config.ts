import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace UniswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimit: number;
    ttl: number;
    uniswapV2RouterAddress: (network: string) => string;
    uniswapV3RouterAddress: (network: string) => string;
    uniswapV3NftManagerAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'uniswap.allowedSlippage'
    ),
    gasLimit: ConfigManagerV2.getInstance().get('uniswap.gasLimit'),
    ttl: ConfigManagerV2.getInstance().get('uniswap.ttl'),
    uniswapV2RouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'uniswap.contractAddresses.' + network + '.uniswapV2RouterAddress'
      ),
    uniswapV3RouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'uniswap.contractAddresses.' + network + '.uniswapV3RouterAddress'
      ),
    uniswapV3NftManagerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'uniswap.contractAddresses.' + network + '.uniswapV3NftManagerAddress'
      ),
    tradingTypes: ['AMM', 'rangeAMM'],
    availableNetworks: [{ chain: 'ethereum', networks: ['mainnet', 'kovan'] }],
  };
}
