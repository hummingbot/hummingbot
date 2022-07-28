import { ConfigManagerV2 } from '../../services/config-manager-v2';

export interface NetworkConfig {
  slug: string;
  rpcUrl: string;
}

export interface Config {
  network: NetworkConfig;
  nativeCurrencySymbol: string;
  tokenProgram: string;
  transactionLamports: number;
  lamportsToSol: number;
  timeToLive: number;
  customRpcUrl: string | undefined;
  rpcAPIKey: string | undefined;
}

export namespace SolanaConfig {
  export const config: Config = getSolanaConfig('solana');
}

export function getSolanaConfig(chainName: string): Config {
  const configManager = ConfigManagerV2.getInstance();
  const network = ConfigManagerV2.getInstance().get(chainName + '.network');
  return {
    network: {
      slug: network,
      rpcUrl: configManager.get(chainName + '.networks.' + network + '.rpcURL'),
    },
    nativeCurrencySymbol: configManager.get(
      chainName + '.networks.' + network + '.nativeCurrencySymbol'
    ),
    tokenProgram: configManager.get(chainName + '.tokenProgram'),
    transactionLamports: configManager.get(chainName + '.transactionLamports'),
    lamportsToSol: configManager.get(chainName + '.lamportsToSol'),
    timeToLive: configManager.get(chainName + '.timeToLive'),
    customRpcUrl: configManager.get(chainName + '.customRpcUrl'),
    rpcAPIKey: configManager.get(chainName + '.rpcAPIKey'),
  };
}
