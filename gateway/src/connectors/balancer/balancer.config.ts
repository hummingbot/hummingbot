import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace BalancerConfig {
  export interface NetworkConfig {
    maximumHops: number;
    allowedSlippage: string;
    gasLimitEstimate: number;
    balancerVaultAddress: (network: string) => string;
    ttl: number;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    maximumHops: ConfigManagerV2.getInstance().get(`balancer.maximumHops`),
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'balancer.allowedSlippage'
    ),
    gasLimitEstimate: ConfigManagerV2.getInstance().get(
      `balancer.gasLimitEstimate`
    ),
    ttl: ConfigManagerV2.getInstance().get('balancer.ttl'),
    balancerVaultAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'balancer.contractAddresses.' + network + '.balancerVaultAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      {
        chain: 'ethereum',
        networks: Object.keys(
          ConfigManagerV2.getInstance().get('balancer.contractAddresses')
        ),
      },
    ],
  };
}
