import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace OpenoceanConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimitEstimate: number;
    ttl: number;
    routerAddress: (chain: string, network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'openocean.allowedSlippage'
    ),
    gasLimitEstimate: ConfigManagerV2.getInstance().get(
      `openocean.gasLimitEstimate`
    ),
    ttl: ConfigManagerV2.getInstance().get('openocean.ttl'),
    routerAddress: (chain: string, network: string) =>
      ConfigManagerV2.getInstance().get(
        'openocean.contractAddresses.' +
          chain +
          '.' +
          network +
          '.routerAddress'
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      { chain: 'avalanche', networks: ['avalanche'] },
      { chain: 'ethereum', networks: ['mainnet'] },
      { chain: 'polygon', networks: ['mainnet'] },
      { chain: 'harmony', networks: ['mainnet'] },
    ],
  };
}
