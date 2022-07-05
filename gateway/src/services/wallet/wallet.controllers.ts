import fse from 'fs-extra';
import { Avalanche } from '../../chains/avalanche/avalanche';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { Polygon } from '../../chains/polygon/polygon';
import { Solana } from '../../chains/solana/solana';
import { Harmony } from '../../chains/harmony/harmony';

import {
  AddWalletRequest,
  AddWalletResponse,
  RemoveWalletRequest,
  GetWalletResponse,
} from './wallet.requests';

import { ConfigManagerCertPassphrase } from '../config-manager-cert-passphrase';

import {
  HttpException,
  UNKNOWN_CHAIN_ERROR_CODE,
  UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE,
} from '../error-handler';

const walletPath = './conf/wallets';

export async function mkdirIfDoesNotExist(path: string): Promise<void> {
  const exists = await fse.pathExists(path);
  if (!exists) {
    await fse.mkdir(path, { recursive: true });
  }
}

export async function addWallet(
  req: AddWalletRequest
): Promise<AddWalletResponse> {
  const passphrase = ConfigManagerCertPassphrase.readPassphrase();
  if (!passphrase) {
    throw new Error('There is no passphrase');
  }
  let address: string;
  let encryptedPrivateKey: string;
  if (req.chain === 'ethereum') {
    const ethereum = Ethereum.getInstance(req.network);
    address = ethereum.getWalletFromPrivateKey(req.privateKey).address;
    encryptedPrivateKey = await ethereum.encrypt(req.privateKey, passphrase);
  } else if (req.chain === 'avalanche') {
    const avalanche = Avalanche.getInstance(req.network);
    address = avalanche.getWalletFromPrivateKey(req.privateKey).address;
    encryptedPrivateKey = await avalanche.encrypt(req.privateKey, passphrase);
  } else if (req.chain === 'polygon') {
    const polygon = Polygon.getInstance(req.network);
    address = polygon.getWalletFromPrivateKey(req.privateKey).address;
    encryptedPrivateKey = await polygon.encrypt(req.privateKey, passphrase);
  } else if (req.chain === 'solana') {
    const solana = await Solana.getInstance(req.network);
    address = solana
      .getKeypairFromPrivateKey(req.privateKey)
      .publicKey.toBase58();
    encryptedPrivateKey = await solana.encrypt(req.privateKey, passphrase);
  } else if (req.chain === 'harmony') {
    const harmony = Harmony.getInstance(req.network);
    address = harmony.getWalletFromPrivateKey(req.privateKey).address;
    encryptedPrivateKey = await harmony.encrypt(req.privateKey, passphrase);
  } else {
    throw new HttpException(
      500,
      UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE(req.chain),
      UNKNOWN_CHAIN_ERROR_CODE
    );
  }

  const path = `${walletPath}/${req.chain}`;
  await mkdirIfDoesNotExist(path);
  await fse.writeFile(`${path}/${address}.json`, encryptedPrivateKey);
  return { address };
}

// if the file does not exist, this should not fail
export async function removeWallet(req: RemoveWalletRequest): Promise<void> {
  await fse.rm(`./conf/wallets/${req.chain}/${req.address}.json`, {
    force: true,
  });
}

export async function getDirectories(source: string): Promise<string[]> {
  await mkdirIfDoesNotExist(walletPath);
  const files = await fse.readdir(source, { withFileTypes: true });
  return files
    .filter((dirent) => dirent.isDirectory())
    .map((dirent) => dirent.name);
}

export function getLastPath(path: string): string {
  return path.split('/').slice(-1)[0];
}

export function dropExtension(path: string): string {
  return path.substr(0, path.lastIndexOf('.')) || path;
}

export async function getJsonFiles(source: string): Promise<string[]> {
  const files = await fse.readdir(source, { withFileTypes: true });
  return files
    .filter((f) => f.isFile() && f.name.endsWith('.json'))
    .map((f) => f.name);
}

export async function getWallets(): Promise<GetWalletResponse[]> {
  const chains = await getDirectories(walletPath);

  const responses: GetWalletResponse[] = [];

  for (const chain of chains) {
    const walletFiles = await getJsonFiles(`${walletPath}/${chain}`);

    const response: GetWalletResponse = { chain, walletAddresses: [] };

    for (const walletFile of walletFiles) {
      const address = dropExtension(getLastPath(walletFile));
      response.walletAddresses.push(address);
    }

    responses.push(response);
  }

  return responses;
}
