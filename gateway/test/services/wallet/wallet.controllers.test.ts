import { patch, unpatch } from '../patch';
import { Ethereum } from '../../../src/chains/ethereum/ethereum';
import { Avalanche } from '../../../src/chains/avalanche/avalanche';
import { Harmony } from '../../../src/chains/harmony/harmony';

import {
  addWallet,
  getWallets,
  removeWallet,
} from '../../../src/services/wallet/wallet.controllers';
import {
  ACCOUNT_NOT_SPECIFIED_CODE,
  ACCOUNT_NOT_SPECIFIED_ERROR_MESSAGE,
  HttpException,
  UNKNOWN_CHAIN_ERROR_CODE,
  UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE,
} from '../../../src/services/error-handler';

import { ConfigManagerCertPassphrase } from '../../../src/services/config-manager-cert-passphrase';
import { BinanceSmartChain } from '../../../src/chains/binance-smart-chain/binance-smart-chain';
import { Cronos } from '../../../src/chains/cronos/cronos';
import { Near } from '../../../src/chains/near/near';

let avalanche: Avalanche;
let cronos: Cronos;
let eth: Ethereum;
let harmony: Harmony;
let bsc: BinanceSmartChain;
let near: Near;

beforeAll(async () => {
  patch(ConfigManagerCertPassphrase, 'readPassphrase', () => 'a');

  avalanche = Avalanche.getInstance('fuji');
  eth = Ethereum.getInstance('kovan');
  harmony = Harmony.getInstance('testnet');
  bsc = BinanceSmartChain.getInstance('testnet');
  cronos = Cronos.getInstance('testnet');
  near = Near.getInstance('testnet');
});

beforeEach(() =>
  patch(ConfigManagerCertPassphrase, 'readPassphrase', () => 'a')
);

afterAll(async () => {
  await avalanche.close();
  await eth.close();
  await harmony.close();
  await bsc.close();
  await cronos.close();
  await near.close();
});

afterEach(() => unpatch());

const oneAddress = '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf';

const onePrivateKey =
  '0000000000000000000000000000000000000000000000000000000000000001'; // noqa: mock

// encoding of onePrivateKey with the password 'a'
const encodedPrivateKey = {
  address: '7e5f4552091a69125d5dfcb7b8c2659029395bdf',
  id: '7bb58a6c-06d3-4ede-af06-5f4a5cb87f0b',
  version: 3,
  Crypto: {
    cipher: 'aes-128-ctr',
    cipherparams: { iv: '60276d7bf5fa57ce0ae8e65fc578c3ac' },
    ciphertext:
      'be98ee3d44744e1417531b15a7b1e47b945cfc100d3ff2680f757a824840fb67', // noqa: mock
    kdf: 'scrypt',
    kdfparams: {
      salt: '90b7e0017b4f9df67aa5f2de73495c14de086b8abb5b68ce3329596eb14f991c', // noqa: mock
      n: 131072,
      dklen: 32,
      p: 1,
      r: 8,
    },
    mac: '0cea1492f67ed43234b69100d873e17b4a289dd508cf5e866a3b18599ff0a5fc', // noqa: mock
  },
};

describe('addWallet and getWallets', () => {
  it('add an Ethereum wallet', async () => {
    patch(eth, 'getWallet', () => {
      return {
        address: oneAddress,
      };
    });

    patch(eth, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await addWallet({
      privateKey: onePrivateKey,
      chain: 'ethereum',
      network: 'kovan',
    });

    const wallets = await getWallets();

    const addresses: string[][] = wallets
      .filter((wallet) => wallet.chain === 'ethereum')
      .map((wallet) => wallet.walletAddresses);

    expect(addresses[0]).toContain(oneAddress);
  });

  it('add an Avalanche wallet', async () => {
    patch(avalanche, 'getWallet', () => {
      return {
        address: oneAddress,
      };
    });

    patch(avalanche, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await addWallet({
      privateKey: onePrivateKey,
      chain: 'avalanche',
      network: 'fuji',
    });

    const wallets = await getWallets();

    const addresses: string[][] = wallets
      .filter((wallet) => wallet.chain === 'avalanche')
      .map((wallet) => wallet.walletAddresses);

    expect(addresses[0]).toContain(oneAddress);
  });

  it('add an Harmony wallet', async () => {
    patch(harmony, 'getWallet', () => {
      return {
        address: oneAddress,
      };
    });

    patch(harmony, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await addWallet({
      privateKey: onePrivateKey,
      chain: 'harmony',
      network: 'testnet',
    });

    const wallets = await getWallets();

    const addresses: string[][] = wallets
      .filter((wallet) => wallet.chain === 'harmony')
      .map((wallet) => wallet.walletAddresses);

    expect(addresses[0]).toContain(oneAddress);
  });

  it('add a Binance Smart Chain wallet', async () => {
    patch(bsc, 'getWallet', () => {
      return {
        address: oneAddress,
      };
    });

    patch(bsc, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await addWallet({
      privateKey: onePrivateKey,
      chain: 'binance-smart-chain',
      network: 'testnet',
    });

    const wallets = await getWallets();

    const addresses: string[][] = wallets
      .filter((wallet) => wallet.chain === 'binance-smart-chain')
      .map((wallet) => wallet.walletAddresses);

    expect(addresses[0]).toContain(oneAddress);
  });

  it('add a Cronos wallet', async () => {
    patch(cronos, 'getWallet', () => {
      return {
        address: oneAddress,
      };
    });

    patch(cronos, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await addWallet({
      privateKey: onePrivateKey,
      chain: 'cronos',
      network: 'testnet',
    });

    const wallets = await getWallets();

    const addresses: string[][] = wallets
      .filter((wallet) => wallet.chain === 'cronos')
      .map((wallet) => wallet.walletAddresses);

    expect(addresses[0]).toContain(oneAddress);
  });

  it('fail to add a wallet to unknown chain', async () => {
    await expect(
      addWallet({
        privateKey: onePrivateKey,
        chain: 'shibainu',
        network: 'doge',
      })
    ).rejects.toThrow(
      new HttpException(
        500,
        UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE('shibainu'),
        UNKNOWN_CHAIN_ERROR_CODE
      )
    );
  });

  it('fail to add a wallet if account is not specified when adding near wallet', async () => {
    await expect(
      addWallet({
        privateKey: onePrivateKey,
        chain: 'near',
        network: 'testnet',
      })
    ).rejects.toThrow(
      new HttpException(
        500,
        ACCOUNT_NOT_SPECIFIED_ERROR_MESSAGE(),
        ACCOUNT_NOT_SPECIFIED_CODE
      )
    );
  });
});

describe('addWallet and removeWallets', () => {
  it('remove an Ethereum wallet', async () => {
    patch(eth, 'getWallet', () => {
      return {
        address: oneAddress,
      };
    });

    patch(eth, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    patch(eth, 'getWalletFromPrivateKey', () => {
      return {
        address: oneAddress,
      };
    });

    await addWallet({
      privateKey: onePrivateKey,
      chain: 'ethereum',
      network: 'kovan',
    });

    await removeWallet({ chain: 'ethereum', address: oneAddress });

    const wallets = await getWallets();

    const addresses: string[][] = wallets
      .filter((wallet) => wallet.chain === 'ethereum')
      .map((wallet) => wallet.walletAddresses);

    expect(addresses[0]).not.toContain(oneAddress);
  });

  it('remove an Harmony wallet', async () => {
    patch(harmony, 'getWallet', () => {
      return {
        address: oneAddress,
      };
    });

    patch(harmony, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await addWallet({
      privateKey: onePrivateKey,
      chain: 'harmony',
      network: 'testnet',
    });

    await removeWallet({ chain: 'harmony', address: oneAddress });

    const wallets = await getWallets();

    const addresses: string[][] = wallets
      .filter((wallet) => wallet.chain === 'harmony')
      .map((wallet) => wallet.walletAddresses);

    expect(addresses[0]).not.toContain(oneAddress);
  });
});
