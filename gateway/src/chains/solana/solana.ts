import {
  Account as TokenAccount,
  getOrCreateAssociatedTokenAccount,
} from '@solana/spl-token';
import { TokenInfo, TokenListProvider } from '@solana/spl-token-registry';
import {
  Account,
  AccountInfo,
  Commitment,
  Connection,
  Keypair,
  LogsCallback,
  LogsFilter,
  ParsedAccountData,
  PublicKey,
  SlotUpdateCallback,
  TokenAmount,
  TransactionResponse,
} from '@solana/web3.js';
import bs58 from 'bs58';
import { BigNumber } from 'ethers';
import fse from 'fs-extra';
import NodeCache from 'node-cache';
import { Cache, CacheContainer } from 'node-ts-cache';
import { MemoryStorage } from 'node-ts-cache-storage-memory';
import { runWithRetryAndTimeout } from '../../connectors/serum/serum.helpers';
import { countDecimals, TokenValue, walletPath } from '../../services/base';
import { ConfigManagerCertPassphrase } from '../../services/config-manager-cert-passphrase';
import { logger } from '../../services/logger';
import { getSolanaConfig } from './solana.config';
import { TransactionResponseStatusCode } from './solana.requests';

const crypto = require('crypto').webcrypto;

const caches = {
  instances: new CacheContainer(new MemoryStorage()),
};

export class Solana implements Solanaish {
  public rpcUrl;
  public transactionLamports;
  public cache: NodeCache;

  protected tokenList: TokenInfo[] = [];
  private _tokenMap: Record<string, TokenInfo> = {};
  private _tokenAddressMap: Record<string, TokenInfo> = {};
  private _keypairs: Record<string, Keypair> = {};

  private static _instances: { [name: string]: Solana };

  private _requestCount: number;
  private readonly _connection: Connection;
  private readonly _lamportPrice: number;
  private readonly _lamportDecimals: number;
  private readonly _nativeTokenSymbol: string;
  private readonly _tokenProgramAddress: PublicKey;
  private readonly _network: string;
  private readonly _metricsLogInterval: number;
  // there are async values set in the constructor
  private _ready: boolean = false;
  private initializing: boolean = false;

  constructor(network: string) {
    this._network = network;

    const config = getSolanaConfig('solana', network);

    this.rpcUrl = config.network.nodeUrl;

    this._connection = new Connection(this.rpcUrl, 'processed' as Commitment);
    this.cache = new NodeCache({ stdTTL: 3600 }); // set default cache ttl to 1hr

    this._nativeTokenSymbol = 'SOL';
    this._tokenProgramAddress = new PublicKey(config.tokenProgram);

    this.transactionLamports = config.transactionLamports;
    this._lamportPrice = config.lamportsToSol;
    this._lamportDecimals = countDecimals(this._lamportPrice);

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    this.onDebugMessage('all', this.requestCounter.bind(this));
    setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
  }

  public get gasPrice(): number {
    return this._lamportPrice;
  }

  @Cache(caches.instances, { isCachedForever: true })
  public static getInstance(network: string): Solana {
    if (Solana._instances === undefined) {
      Solana._instances = {};
    }
    if (!(network in Solana._instances)) {
      Solana._instances[network] = new Solana(network);
    }

    return Solana._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Solana } {
    return this._instances;
  }

  public get connection() {
    return this._connection;
  }

  public onNewSlot(func: SlotUpdateCallback) {
    this._connection.onSlotUpdate(func);
  }

  public onDebugMessage(filter: LogsFilter, func: LogsCallback) {
    this._connection.onLogs(filter, func);
  }

  async init(): Promise<void> {
    if (!this.ready() && !this.initializing) {
      this.initializing = true;
      await this.loadTokens();
      this._ready = true;
      this.initializing = false;
    }
  }

  ready(): boolean {
    return this._ready;
  }

  async loadTokens(): Promise<void> {
    this.tokenList = await this.getTokenList();
    this.tokenList.forEach((token: TokenInfo) => {
      this._tokenMap[token.symbol] = token;
      this._tokenAddressMap[token.address] = token;
    });
  }

  // returns a Tokens for a given list source and list type
  async getTokenList(): Promise<TokenInfo[]> {
    const tokenListProvider = new TokenListProvider();
    const tokens = await runWithRetryAndTimeout(
      tokenListProvider,
      tokenListProvider.resolve,
      []
    );

    return tokens.filterByClusterSlug(this._network).getList();
  }

  // returns the price of 1 lamport in SOL
  public get lamportPrice(): number {
    return this._lamportPrice;
  }

  // solana token lists are large. instead of reloading each time with
  // getTokenList, we can read the stored tokenList value from when the
  // object was initiated.
  public get storedTokenList(): TokenInfo[] {
    return Object.values(this._tokenMap);
  }

  // return the TokenInfo object for a symbol
  getTokenForSymbol(symbol: string): TokenInfo | null {
    return this._tokenMap[symbol] ?? null;
  }

  // return the TokenInfo object for a symbol
  getTokenForMintAddress(mintAddress: PublicKey): TokenInfo | null {
    return this._tokenAddressMap[mintAddress.toString()]
      ? this._tokenAddressMap[mintAddress.toString()]
      : null;
  }

  // returns Keypair for a private key, which should be encoded in Base58
  getKeypairFromPrivateKey(privateKey: string): Keypair {
    const decoded = bs58.decode(privateKey);

    return Keypair.fromSecretKey(decoded);
  }

  async getAccount(address: string): Promise<Account> {
    const keypair = await this.getKeypair(address);

    return new Account(keypair.secretKey);
  }

  /**
   *
   * @param walletAddress
   * @param tokenMintAddress
   */
  async findAssociatedTokenAddress(
    walletAddress: PublicKey,
    tokenMintAddress: PublicKey
  ): Promise<PublicKey> {
    const tokenProgramId = this._tokenProgramAddress;
    const splAssociatedTokenAccountProgramId = (
      await runWithRetryAndTimeout(
        this.connection,
        this.connection.getParsedTokenAccountsByOwner,
        [
          walletAddress,
          {
            programId: this._tokenProgramAddress,
          },
        ]
      )
    ).value.map((item) => item.pubkey)[0];

    const programAddress = (
      await runWithRetryAndTimeout(PublicKey, PublicKey.findProgramAddress, [
        [
          walletAddress.toBuffer(),
          tokenProgramId.toBuffer(),
          tokenMintAddress.toBuffer(),
        ],
        splAssociatedTokenAccountProgramId,
      ])
    )[0];

    return programAddress;
  }

  async getKeypair(address: string): Promise<Keypair> {
    if (!this._keypairs[address]) {
      const path = `${walletPath}/solana`;

      const encryptedPrivateKey: any = JSON.parse(
        await fse.readFile(`${path}/${address}.json`, 'utf8'),
        (key, value) => {
          switch (key) {
            case 'ciphertext':
            case 'salt':
            case 'iv':
              return bs58.decode(value);
            default:
              return value;
          }
        }
      );

      const passphrase = ConfigManagerCertPassphrase.readPassphrase();
      if (!passphrase) {
        throw new Error('missing passphrase');
      }
      this._keypairs[address] = await this.decrypt(
        encryptedPrivateKey,
        passphrase
      );
    }

    return this._keypairs[address];
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

  // Takes a base58 encoded privateKey and saves it to a json
  async encrypt(privateKey: string, password: string): Promise<string> {
    const iv = crypto.getRandomValues(new Uint8Array(16));
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const keyMaterial = await Solana.getKeyMaterial(password);
    const keyAlgorithm = {
      name: 'PBKDF2',
      salt: salt,
      iterations: 500000,
      hash: 'SHA-256',
    };
    const key = await Solana.getKey(keyAlgorithm, keyMaterial);
    const cipherAlgorithm = {
      name: 'AES-GCM',
      iv: iv,
    };
    const enc = new TextEncoder();
    const ciphertext: Uint8Array = (await crypto.subtle.encrypt(
      cipherAlgorithm,
      key,
      enc.encode(privateKey)
    )) as Uint8Array;
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
            return bs58.encode(Uint8Array.from(Object.values(value)));
          default:
            return value;
        }
      }
    );
  }

  async decrypt(encryptedPrivateKey: any, password: string): Promise<Keypair> {
    const keyMaterial = await Solana.getKeyMaterial(password);
    const key = await Solana.getKey(
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
    return Keypair.fromSecretKey(bs58.decode(dec.decode(decrypted)));
  }

  async getBalances(wallet: Keypair): Promise<Record<string, TokenValue>> {
    const balances: Record<string, TokenValue> = {};

    balances['SOL'] = await runWithRetryAndTimeout(this, this.getSolBalance, [
      wallet,
    ]);

    const allSplTokens = await runWithRetryAndTimeout(
      this.connection,
      this.connection.getParsedTokenAccountsByOwner,
      [wallet.publicKey, { programId: this._tokenProgramAddress }]
    );

    allSplTokens.value.forEach(
      (tokenAccount: {
        pubkey: PublicKey;
        account: AccountInfo<ParsedAccountData>;
      }) => {
        const tokenInfo = tokenAccount.account.data.parsed['info'];
        const symbol = this.getTokenForMintAddress(tokenInfo['mint'])?.symbol;
        if (symbol != null && symbol.toUpperCase() !== 'SOL')
          balances[symbol.toUpperCase()] = this.tokenResponseToTokenValue(
            tokenInfo['tokenAmount']
          );
      }
    );

    return balances;
  }

  // returns the SOL balance, convert BigNumber to string
  async getSolBalance(wallet: Keypair): Promise<TokenValue> {
    const lamports = await runWithRetryAndTimeout(
      this.connection,
      this.connection.getBalance,
      [wallet.publicKey]
    );
    return { value: BigNumber.from(lamports), decimals: this._lamportDecimals };
  }

  tokenResponseToTokenValue(account: TokenAmount): TokenValue {
    return {
      value: BigNumber.from(account.amount),
      decimals: account.decimals,
    };
  }

  // returns the balance for an SPL token
  public async getSplBalance(
    walletAddress: PublicKey,
    mintAddress: PublicKey
  ): Promise<TokenValue> {
    const response = await runWithRetryAndTimeout(
      this.connection,
      this.connection.getParsedTokenAccountsByOwner,
      [walletAddress, { mint: mintAddress }]
    );
    if (response['value'].length == 0) {
      throw new Error(`Token account not initialized`);
    }
    return this.tokenResponseToTokenValue(
      response.value[0].account.data.parsed['info']['tokenAmount']
    );
  }

  // returns whether the token account is initialized, given its mint address
  async isTokenAccountInitialized(
    walletAddress: PublicKey,
    mintAddress: PublicKey
  ): Promise<boolean> {
    const response = await runWithRetryAndTimeout(
      this.connection,
      this.connection.getParsedTokenAccountsByOwner,
      [walletAddress, { programId: this._tokenProgramAddress }]
    );
    for (const accountInfo of response.value) {
      if (
        accountInfo.account.data.parsed['info']['mint'] ==
        mintAddress.toBase58()
      )
        return true;
    }
    return false;
  }

  // returns token account if is initialized, given its mint address
  public async getTokenAccount(
    walletAddress: PublicKey,
    mintAddress: PublicKey
  ): Promise<{
    pubkey: PublicKey;
    account: AccountInfo<ParsedAccountData>;
  } | null> {
    const response = await runWithRetryAndTimeout(
      this.connection,
      this.connection.getParsedTokenAccountsByOwner,
      [walletAddress, { programId: this._tokenProgramAddress }]
    );
    for (const accountInfo of response.value) {
      if (
        accountInfo.account.data.parsed['info']['mint'] ==
        mintAddress.toBase58()
      )
        return accountInfo;
    }
    return null;
  }

  // Gets token account information, or creates a new token account for given token mint address
  // if needed, which costs 0.035 SOL
  async getOrCreateAssociatedTokenAccount(
    wallet: Keypair,
    tokenAddress: PublicKey
  ): Promise<TokenAccount | null> {
    return getOrCreateAssociatedTokenAccount(
      this._connection,
      wallet,
      tokenAddress,
      wallet.publicKey
    );
  }

  // returns an ethereum TransactionResponse for a txHash.
  async getTransaction(
    payerSignature: string
  ): Promise<TransactionResponse | null> {
    if (this.cache.keys().includes(payerSignature)) {
      // If it's in the cache, return the value in cache, whether it's null or not
      return this.cache.get(payerSignature) as TransactionResponse;
    } else {
      // If it's not in the cache,
      const fetchedTx = runWithRetryAndTimeout(
        this._connection,
        this._connection.getTransaction,
        [
          payerSignature,
          {
            commitment: 'confirmed',
          },
        ]
      );

      this.cache.set(payerSignature, fetchedTx); // Cache the fetched receipt, whether it's null or not

      return fetchedTx;
    }
  }

  // returns an ethereum TransactionResponseStatusCode for a txData.
  public async getTransactionStatusCode(
    txData: TransactionResponse | null
  ): Promise<TransactionResponseStatusCode> {
    let txStatus;
    if (!txData) {
      // tx not found, didn't reach the mempool or it never existed
      txStatus = TransactionResponseStatusCode.FAILED;
    } else {
      txStatus =
        txData.meta?.err == null
          ? TransactionResponseStatusCode.CONFIRMED
          : TransactionResponseStatusCode.FAILED;

      // TODO implement TransactionResponseStatusCode PROCESSED, FINALISED,
      //  based on how many blocks ago the Transaction was
    }
    return txStatus;
  }

  // caches transaction receipt once they arrive
  cacheTransactionReceipt(tx: TransactionResponse) {
    // first (payer) signature is used as cache key since it is unique enough
    this.cache.set(tx.transaction.signatures[0], tx);
  }

  public getTokenBySymbol(tokenSymbol: string): TokenInfo | undefined {
    return this.tokenList.find(
      (token: TokenInfo) =>
        token.symbol.toUpperCase() === tokenSymbol.toUpperCase()
    );
  }

  // returns the current slot number
  async getCurrentSlotNumber(): Promise<number> {
    return await runWithRetryAndTimeout(
      this._connection,
      this._connection.getSlot,
      []
    );
  }

  public requestCounter(msg: any): void {
    if (msg.action === 'request') this._requestCount += 1;
  }

  public metricLogger(): void {
    logger.info(
      this.requestCount +
        ' request(s) sent in last ' +
        this.metricsLogInterval / 1000 +
        ' seconds.'
    );
    this._requestCount = 0; // reset
  }

  public get network(): string {
    return this._network;
  }

  public get nativeTokenSymbol(): string {
    return this._nativeTokenSymbol;
  }

  public get requestCount(): number {
    return this._requestCount;
  }

  public get metricsLogInterval(): number {
    return this._metricsLogInterval;
  }

  // returns the current block number
  async getCurrentBlockNumber(): Promise<number> {
    return await runWithRetryAndTimeout(
      this.connection,
      this.connection.getSlot,
      ['processed']
    );
  }

  async close() {
    if (this._network in Solana._instances) {
      delete Solana._instances[this._network];
    }
  }
}

export type Solanaish = Solana;
export const Solanaish = Solana;
