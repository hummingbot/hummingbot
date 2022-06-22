import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace PancakeswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    ttl: number;
    routerAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'pancakeswap.allowedSlippage'
    ),
    ttl: ConfigManagerV2.getInstance().get('pancakeswap.ttl'),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'pancakeswap.contractAddresses.' + network + '.routerAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [{ chain: 'bsc', networks: ['mainnet', 'testnet'] }],
  };
}
