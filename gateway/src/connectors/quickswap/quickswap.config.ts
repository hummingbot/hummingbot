import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace QuickswapConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimit: number;
    ttl: number;
    routerAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'quickswap.allowedSlippage'
    ),
    gasLimit: ConfigManagerV2.getInstance().get('quickswap.gasLimit'),
    ttl: ConfigManagerV2.getInstance().get('quickswap.ttl'),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'quickswap.contractAddresses.' + network + '.routerAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [{ chain: 'polygon', networks: ['mainnet', 'mumbai'] }],
  };
}
