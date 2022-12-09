export interface AddWalletRequest {
  chain: string;
  network: string;
  privateKey: string;
  address?: string;
}

export interface AddWalletResponse {
  address: string;
}

export interface RemoveWalletRequest {
  chain: string;
  address: string;
}

export interface GetWalletResponse {
  chain: string;
  walletAddresses: string[];
}
