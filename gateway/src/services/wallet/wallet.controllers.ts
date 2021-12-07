import fse from 'fs-extra';
import { Ethereumish } from '../ethereumish.interface';

import {
  AddWalletRequest,
  RemoveWalletRequest,
  GetWalletResponse,
} from './wallet.requests';
import { ConfigManagerCertPassphrase } from '../config-manager-cert-passphrase';

export async function addWallet(
  ethereum: Ethereumish,
  req: AddWalletRequest
): Promise<void> {
  const wallet = ethereum.getWallet(req.privateKey);
  const passphrase = ConfigManagerCertPassphrase.readPassphrase();
  if (passphrase) {
    const encryptedPrivateKey = ethereum.encrypt(req.privateKey, passphrase);
    await fse.writeFile(
      `./conf/wallets/${req.chainName}/${wallet.address}.json`,
      encryptedPrivateKey
    );
  } else {
    throw new Error('');
  }
}

// if the file does not exist, this should not fail
export async function removeWallet(req: RemoveWalletRequest): Promise<void> {
  await fse.rm(`./conf/wallets/${req.chainName}/${req.address}.json`, {
    force: true,
  });
}

export async function getWallets(): Promise<GetWalletResponse[]> {
  return [];
}
