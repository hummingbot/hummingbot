import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace UniswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimit: number;
    ttl: number;
    uniswapV2RouterAddress: string;
    uniswapV3RouterAddress: string;
    uniswapV3NftManagerAddress: string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  const eth_network = ConfigManagerV2.getInstance().get('ethereum.network');

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'uniswap.allowedSlippage'
    ),
    gasLimit: ConfigManagerV2.getInstance().get('uniswap.gasLimit'),
    ttl: ConfigManagerV2.getInstance().get('uniswap.ttl'),
    uniswapV2RouterAddress: ConfigManagerV2.getInstance().get(
      'uniswap.contractAddresses.' + eth_network + '.uniswapV2RouterAddress'
    ),
    uniswapV3RouterAddress: ConfigManagerV2.getInstance().get(
      'uniswap.contractAddresses.' + eth_network + '.uniswapV3RouterAddress'
    ),
    uniswapV3NftManagerAddress: ConfigManagerV2.getInstance().get(
      'uniswap.contractAddresses.' + eth_network + '.uniswapV3NftManagerAddress'
    ),
    tradingTypes: ['AMM', 'rangeAMM'],
    availableNetworks: [{ chain: 'ethereum', networks: ['mainnet', 'kovan'] }],
  };
}
