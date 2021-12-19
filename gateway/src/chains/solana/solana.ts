import { logger } from '../../services/logger';
import { ConfigManager } from '../../services/config-manager';
import { TokenValue, countDecimals } from '../../services/base';
import NodeCache from 'node-cache';
import bs58 from 'bs58';
import { BigNumber } from 'ethers';
import {
  Commitment,
  Connection,
  PublicKey,
  Keypair,
  TokenAmount,
  LogsFilter,
  LogsCallback,
  SlotUpdateCallback,
  TransactionResponse,
  AccountInfo,
  ParsedAccountData,
} from '@solana/web3.js';
import {
  Token as TokenProgram,
  AccountInfo as TokenAccount,
} from '@solana/spl-token';
import { TokenListProvider, TokenInfo } from '@solana/spl-token-registry';
import { TransactionResponseStatusCode } from './solana.requests';

export type Solanaish = Solana;

export class Solana {
  public rpcUrl;
  public transactionLamports;
  public cache: NodeCache;

  protected tokenList: TokenInfo[] = [];
  private _tokenMap: Record<string, TokenInfo> = {};
  private _tokenAddressMap: Record<string, TokenInfo> = {};

  private static _instance: Solana;

  private _requestCount: number;
  private readonly _connection: Connection;
  private readonly _lamportPrice: number;
  private readonly _lamportDecimals: number;
  private readonly _nativeTokenSymbol: string;
  private readonly _tokenProgramAddress: PublicKey;
  private readonly _cluster: string;
  private readonly _metricsLogInterval: number;
  // there are async values set in the constructor
  private _ready: boolean = false;
  private _initializing: boolean = false;
  private _initPromise: Promise<void> = Promise.resolve();

  constructor() {
    this._cluster = ConfigManager.config.SOLANA_CLUSTER;

    if (ConfigManager.config.SOLANA_CUSTOM_RPC == null) {
      switch (this._cluster) {
        case 'mainnet-beta':
          this.rpcUrl = 'https://mainnet.infura.io/v3/';
          break;
        case 'devnet':
          this.rpcUrl = 'https://api.devnet.solana.com';
          break;
        case 'testnet':
          this.rpcUrl = 'https://api.testnet.solana.com';
          break;
        default:
          throw new Error('SOLANA_CHAIN not valid');
      }
    } else {
      this.rpcUrl = ConfigManager.config.SOLANA_CUSTOM_RPC;
    }

    this._connection = new Connection(this.rpcUrl, 'processed' as Commitment);
    this.cache = new NodeCache({ stdTTL: 3600 }); // set default cache ttl to 1hr

    this._nativeTokenSymbol = 'SOL';
    this._tokenProgramAddress = new PublicKey(
      ConfigManager.config.SOLANA_TOKEN_PROGRAM
    );

    this.transactionLamports = ConfigManager.config.SOLANA_TRANSACTION_LAMPORTS;
    this._lamportPrice = ConfigManager.config.SOLANA_LAMPORTS_TO_SOL;
    this._lamportDecimals = countDecimals(this._lamportPrice);

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    this.onDebugMessage('all', this.requestCounter.bind(this));
    setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
  }

  public get gasPrice(): number {
    return this._lamportPrice;
  }

  public static getInstance(): Solana {
    if (!Solana._instance) {
      Solana._instance = new Solana();
    }

    return Solana._instance;
  }

  public static reload(): Solana {
    Solana._instance = new Solana();
    return Solana._instance;
  }

  ready(): boolean {
    return this._ready;
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
    if (!this.ready() && !this._initializing) {
      this._initializing = true;
      this._initPromise = this.loadTokens().then(() => {
        this._ready = true;
        this._initializing = false;
      });
    }
    return this._initPromise;
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
    const tokens = await new TokenListProvider().resolve();
    return tokens.filterByClusterSlug(this._cluster).getList();
  }

  // returns the price of 1 lamport in SOL
  public get lamportPrice(): number {
    return this._lamportPrice;
  }

  // solana token lists are large. instead of reloading each time with
  // getTokenList, we can read the stored tokenList value from when the
  // object was initiated.
  public get storedTokenList(): TokenInfo[] {
    return this.tokenList;
  }

  // return the TokenInfo object for a symbol
  getTokenForSymbol(symbol: string): TokenInfo | null {
    return this._tokenMap[symbol] ? this._tokenMap[symbol] : null;
  }

  // return the TokenInfo object for a symbol
  getTokenForMintAddress(mintAddress: PublicKey): TokenInfo | null {
    return this._tokenAddressMap[mintAddress.toString()]
      ? this._tokenAddressMap[mintAddress.toString()]
      : null;
  }

  // returns Keypair for a private key, which should be encoded in Base58
  getWallet(privateKey: string): Keypair {
    const decoded = bs58.decode(privateKey);
    return Keypair.fromSecretKey(decoded);
  }

  async getBalances(wallet: Keypair): Promise<Record<string, TokenValue>> {
    const balances: Record<string, TokenValue> = {};

    balances['SOL'] = await this.getSolBalance(wallet);

    const allSplTokens = await this.connection.getParsedTokenAccountsByOwner(
      wallet.publicKey,
      { programId: this._tokenProgramAddress }
    );

    allSplTokens.value.forEach(
      (tokenAccount: {
        pubkey: PublicKey;
        account: AccountInfo<ParsedAccountData>;
      }) => {
        const tokenInfo = tokenAccount.account.data.parsed['info'];
        const symbol = this.getTokenForMintAddress(tokenInfo['mint'])?.symbol;
        if (symbol != null)
          balances[symbol] = this.tokenResponseToTokenValue(
            tokenInfo['tokenAmount']
          );
      }
    );

    return balances;
  }

  // returns the SOL balance, convert BigNumber to string
  async getSolBalance(wallet: Keypair): Promise<TokenValue> {
    const lamports = await this.connection.getBalance(wallet.publicKey);
    return { value: BigNumber.from(lamports), decimals: this._lamportDecimals };
  }

  tokenResponseToTokenValue(account: TokenAmount): TokenValue {
    return {
      value: BigNumber.from(account.amount),
      decimals: account.decimals,
    };
  }

  // returns the balance for an SPL token
  async getSplBalance(
    wallet: Keypair,
    mintAddress: PublicKey
  ): Promise<TokenValue> {
    const response = await this.connection.getParsedTokenAccountsByOwner(
      wallet.publicKey,
      { mint: mintAddress }
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
    wallet: Keypair,
    mintAddress: PublicKey
  ): Promise<boolean> {
    const response = await this.connection.getParsedTokenAccountsByOwner(
      wallet.publicKey,
      { programId: this._tokenProgramAddress }
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

  // Gets token account information, or creates a new token account for given token mint address
  // if needed, which costs 0.035 SOL
  async getOrCreateAssociatedTokenAccount(
    wallet: Keypair,
    tokenAddress: PublicKey
  ): Promise<TokenAccount> {
    const tokenProgram = new TokenProgram(
      this._connection,
      tokenAddress,
      this._tokenProgramAddress,
      wallet
    );
    return await tokenProgram.getOrCreateAssociatedAccountInfo(
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
      const fetchedTx = this._connection.getTransaction(payerSignature, {
        commitment: 'confirmed',
      });

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
        typeof txData.meta?.err == null
          ? TransactionResponseStatusCode.PRCESSED
          : TransactionResponseStatusCode.FAILED;

      // TODO implement TransactionResponseStatusCode CONFIRMED, FINALISED
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
    return await this._connection.getSlot();
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

  public get cluster(): string {
    return this._cluster;
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
    return await this.connection.getSlot('processed');
  }
}
