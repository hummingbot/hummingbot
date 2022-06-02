import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace PangolinConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    ttl: number;
    routerAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'pangolin.allowedSlippage'
    ),
    ttl: ConfigManagerV2.getInstance().get('pangolin.ttl'),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'pangolin.contractAddresses.' + network + '.routerAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      { chain: 'avalanche', networks: ['avalanche', 'fuji'] },
    ],
  };
}
