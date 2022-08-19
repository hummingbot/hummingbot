import fse from 'fs-extra';
import { Avalanche } from '../../chains/avalanche/avalanche';
import { BinanceSmartChain } from '../../chains/binance-smart-chain/binance-smart-chain';
import { Cronos } from '../../chains/cronos/cronos';
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
  ERROR_RETRIEVING_WALLET_ADDRESS_ERROR_MESSAGE,
  HttpException,
  ERROR_RETRIEVING_WALLET_ADDRESS_ERROR_CODE,
} from '../error-handler';
import { EthereumBase } from '../ethereum-base';

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
  let connection: EthereumBase | HederaBase | Solana;
  let address: string;
  let encryptedPrivateKey: string;

  if (req.chain === 'ethereum') {
    connection = Ethereum.getInstance(req.network);
  } else if (req.chain === 'avalanche') {
    connection = Avalanche.getInstance(req.network);
  } else if (req.chain === 'polygon') {
    connection = Polygon.getInstance(req.network);
  } else if (req.chain === 'solana') {
    connection = await Solana.getInstance(req.network);
  } else if (req.chain === 'harmony') {
    connection = Harmony.getInstance(req.network);
  } else if (req.chain === 'binance-smart-chain') {
    connection = BinanceSmartChain.getInstance(req.network);
  } else if (req.chain === 'cronos') {
    connection = Cronos.getInstance(req.network);
  } else {
    throw new HttpException(
      500,
      ERROR_RETRIEVING_WALLET_ADDRESS_ERROR_MESSAGE(req.privateKey),
      ERROR_RETRIEVING_WALLET_ADDRESS_ERROR_CODE
    );
  }

  if (!connection.ready()) {
    await connection.init();
  }

  if (connection instanceof Solana) {
    address = connection
      .getKeypairFromPrivateKey(req.privateKey)
      .publicKey.toBase58();
    encryptedPrivateKey = await connection.encrypt(req.privateKey, passphrase);
  } else if (connection instanceof EthereumBase) {
    address = connection.getWalletFromPrivateKey(req.privateKey).address;
    encryptedPrivateKey = await connection.encrypt(req.privateKey, passphrase);
  } else {
    throw new HttpException(
      500,
      ERROR_RETRIEVING_WALLET_ADDRESS_ERROR_MESSAGE(req.privateKey),
      ERROR_RETRIEVING_WALLET_ADDRESS_ERROR_CODE
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
