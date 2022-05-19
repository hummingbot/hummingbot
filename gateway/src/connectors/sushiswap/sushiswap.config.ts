import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace SushiswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimit: number;
    ttl: number;
    sushiswapRouterAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'sushiswap.allowedSlippage'
    ),
    gasLimit: ConfigManagerV2.getInstance().get('sushiswap.gasLimit'),
    ttl: ConfigManagerV2.getInstance().get('sushiswap.ttl'),
    sushiswapRouterAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'sushiswap.contractAddresses.' + network + '.sushiswapRouterAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      { chain: 'ethereum', networks: ['mainnet', 'kovan','ropsten'] },
    ],
  };
}
