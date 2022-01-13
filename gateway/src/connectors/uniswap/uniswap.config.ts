import { ConfigManagerV2 } from '../../services/config-manager-v2';

export namespace UniswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimit: number;
    ttl: number;
    uniswapV2RouterAddress: string;
    uniswapV3RouterAddress: string;
    uniswapV3NftManagerAddress: string;
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
  };
}
