import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace CurveConfig {
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
      'curve.allowedSlippage'
    ),
    gasLimit: ConfigManagerV2.getInstance().get('curve.gasLimit'),
    ttl: ConfigManagerV2.getInstance().get('curve.ttl'),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'curve.contractAddresses.' + network + '.routerAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      { chain: 'ethereum', networks: ['mainnet', 'kovan','ropsten'] },
    ],
  };
}
