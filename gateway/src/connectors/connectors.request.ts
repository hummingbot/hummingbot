import { AvailableNetworks } from '../services/config-manager-types';

export interface ConnectorsResponse {
  connectors: Array<{
    name: string;
    trading_type: Array<string>;
    available_networks: Array<AvailableNetworks>;
    additional_spenders?: Array<string>;
    additional_add_wallet_prompts?: Record<string, string>;
  }>;
}
