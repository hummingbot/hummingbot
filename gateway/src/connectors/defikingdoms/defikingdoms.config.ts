import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';
export namespace DefikingdomsConfig {
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
      `defikingdoms.allowedSlippage`
    ),
    gasLimit: ConfigManagerV2.getInstance().get(`defikingdoms.gasLimit`),
    ttl: ConfigManagerV2.getInstance().get(`defikingdoms.ttl`),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        `defikingdoms.contractAddresses.${network}.routerAddress`
      ),
    tradingTypes: ['EVM_AMM'],
    availableNetworks: [
      {
        chain: 'harmony',
        networks: ['mainnet'],
      },
    ],
  };
}
