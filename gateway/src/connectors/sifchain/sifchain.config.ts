/* WIP */
import { ConfigManagerV2 } from '../../services/config-manager-v2';
import { AvailableNetworks } from '../../services/config-manager-types';

export namespace SifchainConnectorConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
    gasLimit: number;
    ttl: number;
    tradingTypes: Array<string>;
    availableNetworks: Array<AvailableNetworks>;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(
      'sifchainConnector.allowedSlippage'
    ),
    gasLimit: ConfigManagerV2.getInstance().get('sifchainConnector.gasLimit'),
    ttl: ConfigManagerV2.getInstance().get('sifchainConnector.ttl'),
    tradingTypes: ['EVM_AMM'], // TODO: Update trading types
    availableNetworks: [{ chain: 'cosmos', networks: ['mainnet', 'testnet'] }],
  };
}
