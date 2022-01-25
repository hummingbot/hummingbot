import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace PangolinConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimit: number;
    ttl: number;
    routerAddress: string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  const network = ConfigManagerV2.getInstance().get('avalanche.network');

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'pangolin.allowedSlippage'
    ),
    gasLimit: ConfigManagerV2.getInstance().get('pangolin.gasLimit'),
    ttl: ConfigManagerV2.getInstance().get('pangolin.ttl'),
    routerAddress: ConfigManagerV2.getInstance().get(
      'pangolin.contractAddresses.' + network + '.routerAddress'
    ),
    tradingTypes: ['AMM'],
    availableNetworks: [
      { chain: 'avalanche', networks: ['avalanche', 'fuji'] },
    ],
  };
}
