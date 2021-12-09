export interface NetworkConfig {
  rpcUrl: string;
  slug: string;
}
export interface Config {
  devnet: NetworkConfig;
  testnet: NetworkConfig;
  mainnet_beta: NetworkConfig;
}
export namespace SolanaConfig {
  export const config: Config = {
    devnet: {
      rpcUrl: 'https://api.devnet.solana.com',
      slug: 'devnet',
    },
    testnet: {
      rpcUrl: 'https://api.testnet.solana.com',
      slug: 'testnet',
    },
    mainnet_beta: {
      rpcUrl: 'https://mainnet.infura.io/v3/',
      slug: 'mainnet-beta'
    },
  };
}
