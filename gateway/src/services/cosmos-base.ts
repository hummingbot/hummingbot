import axios from 'axios';
import { promises as fs } from 'fs';
import { TokenListType, TokenValue, walletPath } from './base';
import NodeCache from 'node-cache';
import fse from 'fs-extra';
import { ConfigManagerCertPassphrase } from './config-manager-cert-passphrase';
import { BigNumber } from 'ethers';
import {
  AccountData,
  // DecodedTxRaw,
  DirectSignResponse,
} from '@cosmjs/proto-signing';

import { IndexedTx } from '@cosmjs/stargate';

//Cosmos
const { DirectSecp256k1Wallet } = require('@cosmjs/proto-signing');
const { StargateClient } = require('@cosmjs/stargate');
const { toBase64, fromBase64, fromHex } = require('@cosmjs/encoding');
const crypto = require('crypto').webcrypto;
const { assets: assetsRegistry } = require('chain-registry');
export interface Token {
  base: string;
  address: string;
  name: string;
  symbol: string;
  decimals: number;
}

export interface CosmosWallet {
  privKey: Uint8Array;
  pubkey: Uint8Array;
  prefix: 'string';
  getAccounts(): [AccountData];
  signDirect(): DirectSignResponse;
  fromKey(): CosmosWallet;
}

export interface KeyAlgorithm {
  name: string;
  salt: Uint8Array;
  iterations: number;
  hash: string;
}

export interface CipherAlgorithm {
  name: string;
  iv: Uint8Array;
}
export interface EncryptedPrivateKey {
  keyAlgorithm: KeyAlgorithm;
  cipherAlgorithm: CipherAlgorithm;
  ciphertext: Uint8Array;
}

export type NewBlockHandler = (bn: number) => void;

export type NewDebugMsgHandler = (msg: any) => void;

export class CosmosBase {
  private _provider;
  protected tokenList: Token[] = [];
  private _tokenMap: Record<string, Token> = {};

  private _ready: boolean = false;
  private _initializing: boolean = false;
  private _initPromise: Promise<void> = Promise.resolve();

  public chainName;
  public rpcUrl;
  public gasPriceConstant;
  public tokenListSource: string;
  public tokenListType: TokenListType;
  public cache: NodeCache;

  constructor(
    chainName: string,
    rpcUrl: string,
    tokenListSource: string,
    tokenListType: TokenListType,
    gasPriceConstant: number
  ) {
    this._provider = StargateClient.connect(rpcUrl);
    this.chainName = chainName;
    this.rpcUrl = rpcUrl;
    this.gasPriceConstant = gasPriceConstant;
    this.tokenListSource = tokenListSource;
    this.tokenListType = tokenListType;
    this.cache = new NodeCache({ stdTTL: 3600 }); // set default cache ttl to 1hr
  }

  ready(): boolean {
    return this._ready;
  }

  public get provider() {
    return this._provider;
  }

  // public onDebugMessage(func: NewDebugMsgHandler) {
  //   this.provider.on('debug', func);
  // }

  async init(): Promise<void> {
    if (!this.ready() && !this._initializing) {
      this._initializing = true;
      this._initPromise = this.loadTokens(
        this.tokenListSource,
        this.tokenListType
      ).then(() => {
        this._ready = true;
        this._initializing = false;
      });
    }
    return this._initPromise;
  }

  async loadTokens(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<void> {
    this.tokenList = await this.getTokenList(tokenListSource, tokenListType);

    if (this.tokenList) {
      this.tokenList.forEach(
        (token: Token) => (this._tokenMap[token.symbol] = token)
      );
    }
  }

  // returns a Tokens for a given list source and list type
  async getTokenList(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<Token[]> {
    let tokens;
    if (tokenListType === 'URL') {
      ({ data: tokens } = await axios.get(tokenListSource));
    } else {
      ({ tokens } = JSON.parse(await fs.readFile(tokenListSource, 'utf8')));
    }
    return tokens;
  }

  // ethereum token lists are large. instead of reloading each time with
  // getTokenList, we can read the stored tokenList value from when the
  // object was initiated.
  public get storedTokenList(): Token[] {
    return this.tokenList;
  }

  // return the Token object for a symbol
  getTokenForSymbol(symbol: string): Token | null {
    return this._tokenMap[symbol] ? this._tokenMap[symbol] : null;
  }

  async getWalletFromPrivateKey(
    privateKey: string,
    prefix: string
  ): Promise<CosmosWallet> {
    const wallet = await DirectSecp256k1Wallet.fromKey(
      fromHex(privateKey),
      prefix
    );

    // Private key can be exported by using - gaiad keys export [key name] --unsafe --unarmored-hex
    return wallet;
  }

  async getAccountsfromPrivateKey(
    privateKey: string,
    prefix: string
  ): Promise<AccountData> {
    const wallet = await this.getWalletFromPrivateKey(privateKey, prefix);

    const accounts = await wallet.getAccounts();

    return accounts[0];
  }

  // returns Wallet for an address
  // TODO: Abstract-away into base.ts
  async getWallet(address: string): Promise<CosmosWallet> {
    const path = `${walletPath}/${this.chainName}`;

    const encryptedPrivateKey: EncryptedPrivateKey = JSON.parse(
      await fse.readFile(`${path}/${address}.json`, 'utf8'),
      (key, value) => {
        switch (key) {
          case 'ciphertext':
          case 'salt':
          case 'iv':
            return fromBase64(value);
          default:
            return value;
        }
      }
    );

    const passphrase = ConfigManagerCertPassphrase.readPassphrase();
    if (!passphrase) {
      throw new Error('missing passphrase');
    }

    return await this.decrypt(encryptedPrivateKey, passphrase, 'cosmos');
  }

  private static async getKeyMaterial(password: string) {
    const enc = new TextEncoder();
    return await crypto.subtle.importKey(
      'raw',
      enc.encode(password),
      'PBKDF2',
      false,
      ['deriveBits', 'deriveKey']
    );
  }

  private static async getKey(
    keyAlgorithm: {
      salt: Uint8Array;
      name: string;
      iterations: number;
      hash: string;
    },
    keyMaterial: CryptoKey
  ) {
    return await crypto.subtle.deriveKey(
      keyAlgorithm,
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      true,
      ['encrypt', 'decrypt']
    );
  }

  // from Solana.ts
  async encrypt(privateKey: string, password: string): Promise<string> {
    const iv = crypto.getRandomValues(new Uint8Array(16));
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const keyMaterial = await CosmosBase.getKeyMaterial(password);
    const keyAlgorithm = {
      name: 'PBKDF2',
      salt: salt,
      iterations: 500000,
      hash: 'SHA-256',
    };
    const key = await CosmosBase.getKey(keyAlgorithm, keyMaterial);

    const cipherAlgorithm = {
      name: 'AES-GCM',
      iv: iv,
    };
    const enc = new TextEncoder();
    const ciphertext: ArrayBuffer = await crypto.subtle.encrypt(
      cipherAlgorithm,
      key,
      enc.encode(privateKey)
    );

    return JSON.stringify(
      {
        keyAlgorithm,
        cipherAlgorithm,
        ciphertext: new Uint8Array(ciphertext),
      },
      (key, value) => {
        switch (key) {
          case 'ciphertext':
          case 'salt':
          case 'iv':
            return toBase64(value);
          default:
            return value;
        }
      }
    );
  }

  async decrypt(
    encryptedPrivateKey: EncryptedPrivateKey,
    password: string,
    prefix: string
  ): Promise<CosmosWallet> {
    const keyMaterial = await CosmosBase.getKeyMaterial(password);
    const key = await CosmosBase.getKey(
      encryptedPrivateKey.keyAlgorithm,
      keyMaterial
    );
    const decrypted = await crypto.subtle.decrypt(
      encryptedPrivateKey.cipherAlgorithm,
      key,
      encryptedPrivateKey.ciphertext
    );
    const dec = new TextDecoder();
    dec.decode(decrypted);

    return await this.getWalletFromPrivateKey(dec.decode(decrypted), prefix);
  }

  getChainAssetsData(chain: string) {
    return assetsRegistry.find(
      ({ chain_name }: { chain_name: string }) => chain_name === chain
    );
  }

  async getDenomMetadata(provider: any, denom: string): Promise<any> {
    return await provider.queryClient.bank.denomMetadata(denom);
  }

  getTokenDecimals(token: any): number {
    return token ? token.denom_units[token.denom_units.length - 1].exponent : 6; // Last denom unit has the decimal amount we need from our list
  }

  async getBalances(wallet: CosmosWallet): Promise<Record<string, TokenValue>> {
    const balances: Record<string, TokenValue> = {};

    const provider = await this._provider;

    const accounts = await wallet.getAccounts();

    const { address } = accounts[0];

    const allTokens = await provider.getAllBalances(address);
    await Promise.all(
      allTokens.map(async (t: { denom: string; amount: string }) => {
        const token = this.getTokenByBase(t.denom);

        // Not all tokens are added in the registry so we use the denom if the token doesn't exist
        balances[token ? token.symbol : t.denom] = {
          value: BigNumber.from(parseInt(t.amount, 10)),
          decimals: this.getTokenDecimals(token),
        };
      })
    );

    return balances;
  }

  // returns a cosmos tx for a txHash
  async getTransaction(id: string): Promise<IndexedTx> {
    const provider = await this._provider;
    const transaction = await provider.getTx(id);

    if (!transaction) {
      throw new Error('Transaction not found');
    }

    return transaction;
  }

  public getTokenBySymbol(tokenSymbol: string): Token | undefined {
    return this.tokenList.find(
      (token: Token) => token.symbol.toUpperCase() === tokenSymbol.toUpperCase()
    );
  }

  public getTokenByBase(base: string): Token | undefined {
    return this.tokenList.find((token: Token) => token.base === base);
  }

  async getCurrentBlockNumber(): Promise<number> {
    const provider = await this._provider;

    return await provider.getHeight();
  }
}
