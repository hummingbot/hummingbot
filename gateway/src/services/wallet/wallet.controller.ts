// import { Ethereum } from '../../chains/ethereum/ethereum';
// import { Avalanche } from '../../chains/avalanche/avalanche';
import fse from 'fs-extra';
import { Ethereumish } from '../ethereumish.interface';

import { AddWalletRequest, RemoveWalletRequest } from './wallet.requests';
import { ConfigManagerCertPassphrase } from '../config-manager-cert-passphrase';

// export namespace WalletController {
//     export const ethereum = Ethereum.getInstance();
//     export const avalanche = Avalanche.getInstance();

//     export const addWallet =
// };

export async function addWallet(
  ethereum: Ethereumish,
  req: AddWalletRequest
): Promise<void> {
  const wallet = ethereum.getWallet(req.privateKey);
  // wallets/{req.chainName}/{address}.json
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

export async function removeWallet(req: RemoveWalletRequest): Promise<void> {
  await fse.rm(`./conf/wallets/${req.chainName}/${req.address}.json`, {
    force: true,
  });
}
