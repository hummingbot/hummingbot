import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace RefConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimit: number;
    ttl: number;
    routerAddress: (network: string) => string;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(`ref.allowedSlippage`),
    gasLimit: ConfigManagerV2.getInstance().get(`ref.gasLimit`),
    ttl: ConfigManagerV2.getInstance().get(`ref.ttl`),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `ref.contractAddresses.${network}.routerAddress`
      ),
    tradingTypes: ['NEAR_AMM'],
    availableNetworks: [
      {
        chain: 'near',
        networks: ['mainnet', 'testnet'],
      },
    ],
  };
}
