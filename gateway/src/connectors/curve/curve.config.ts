import { AvailableNetworks } from '../../services/config-manager-types';

import { ConfigManagerV2 } from '../../services/config-manager-v2';
export namespace CurveConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;      
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(`curve.allowedSlippage`),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      {
        chain: 'ethereum',
        networks: ['mainnet'],
      },
    ],
  };
}
