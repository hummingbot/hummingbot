import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace RefConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimitEstimate: number;
    ttl: number;
    routerAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(`ref.allowedSlippage`),
    gasLimitEstimate: ConfigManagerV2.getInstance().get(`ref.gasLimitEstimate`),
    ttl: ConfigManagerV2.getInstance().get(`ref.ttl`),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `ref.contractAddresses.${network}.routerAddress`
      ),
    tradingTypes: ['NEAR_AMM'],
    availableNetworks: [
      {
        chain: 'near',
        networks: Object.keys(
          ConfigManagerV2.getInstance().get('ref.contractAddresses')
        ).filter((network) =>
          Object.keys(
            ConfigManagerV2.getInstance().get('near.networks')
          ).includes(network)
        ),
      },
    ],
  };
}
