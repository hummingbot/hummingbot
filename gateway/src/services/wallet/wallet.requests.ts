export interface AddWalletRequest {
  chainName: string;
  privateKey: string;
}

export interface RemoveWalletRequest {
  chainName: string;
  address: string;
}
