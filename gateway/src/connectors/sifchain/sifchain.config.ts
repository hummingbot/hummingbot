import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace SifchainConnectorConfig {
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
      'sifchainConnector.allowedSlippage'
    ),
    gasLimit: ConfigManagerV2.getInstance().get('sifchainConnector.gasLimit'),
    ttl: ConfigManagerV2.getInstance().get('sifchainConnector.ttl'),
    routerAddress: (network: string) =>
      ConfigManagerV2.getInstance().get(
        'sifchainConnector.contractAddresses.' + network + '.routerAddress'
      ),
    tradingTypes: ['EVM_AMM'], // TODO: Update trading types
    availableNetworks: [{ chain: 'cosmos', networks: ['mainnet', 'testnet'] }],
  };
}
