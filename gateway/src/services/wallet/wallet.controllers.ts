import fse from 'fs-extra';
import { Avalanche } from '../../chains/avalanche/avalanche';
import { Ethereum } from '../../chains/ethereum/ethereum';

import {
  AddWalletRequest,
  RemoveWalletRequest,
  GetWalletResponse,
} from './wallet.requests';
import { ConfigManagerCertPassphrase } from '../config-manager-cert-passphrase';

export async function addWallet(
  ethereum: Ethereum,
  avalanche: Avalanche,
  req: AddWalletRequest
): Promise<void> {
  const passphrase = ConfigManagerCertPassphrase.readPassphrase();
  if (!passphrase) {
    throw new Error('');
  }
  let address: string;
  let encryptedPrivateKey: string;
  if (req.chainName === 'ethereum') {
    address = ethereum.getWallet(req.privateKey).address;
    encryptedPrivateKey = await ethereum.encrypt(req.privateKey, passphrase);
  } else if (req.chainName === 'avalanche') {
    address = avalanche.getWallet(req.privateKey).address;
    encryptedPrivateKey = await avalanche.encrypt(req.privateKey, passphrase);
  } else {
    throw new Error('unrecognized chain name');
  }

  await fse.writeFile(
    `./conf/wallets/${req.chainName}/${address}.json`,
    encryptedPrivateKey
  );
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
