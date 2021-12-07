export type chainName = 'ethereum' | 'avalanche';

export interface AddWalletRequest {
  chainName: chainName;
  privateKey: string;
}

export interface RemoveWalletRequest {
  chainName: string;
  address: string;
}

export interface GetWalletResponse {
  chain: string;
  walletAddresses: string[];
}
