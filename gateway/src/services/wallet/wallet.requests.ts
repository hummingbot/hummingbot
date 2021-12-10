export type chainName = 'ethereum' | 'avalanche';

export interface AddWalletRequest {
  chainName: chainName;
  privateKey: string;
}

export interface RemoveWalletRequest {
  chainName: chainName;
  address: string;
}

export interface GetWalletResponse {
  chain: string;
  walletAddresses: string[];
}
