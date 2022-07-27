import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace TraderjoeConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimitEstimate: number;
    ttl: number;
    routerAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'traderjoe.allowedSlippage'
    ),
    gasLimitEstimate: ConfigManagerV2.getInstance().get(
      'traderjoe.gasLimitEstimate'
    ),
    ttl: ConfigManagerV2.getInstance().get('traderjoe.ttl'),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'traderjoe.contractAddresses.' + network + '.routerAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      { chain: 'avalanche', networks: ['avalanche', 'fuji'] },
    ],
  };
}
