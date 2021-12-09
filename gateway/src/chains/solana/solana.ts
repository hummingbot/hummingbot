import { logger } from '../../services/logger';
import { ConfigManager } from '../../services/config-manager';
import { TokenValue, countDecimals} from '../../services/base';
import NodeCache from "node-cache";
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
  SlotUpdateCallback, TransactionResponse
} from "@solana/web3.js";
import {Token as TokenProgram} from "@solana/spl-token";
import {TokenListProvider, TokenInfo} from "@solana/spl-token-registry";

export class Solana {
  public rpcUrl;
  public transactionLamports;
  public cache: NodeCache;

  protected tokenList: TokenInfo[] = [];
  private _tokenMap: Record<string, TokenInfo> = {};

  private static _instance: Solana;

  private _requestCount: number;
  private readonly _connection: Connection;
  private readonly _lamportPrice: number;
  private readonly _lamportDecimals: number;
  private readonly _nativeTokenSymbol: string;
  private readonly _tokenProgramAddress: PublicKey;
  private readonly _chainSlug: string;
  private readonly _metricsLogInterval: number;
  // there are async values set in the constructor
  private _ready: boolean = false;
  private _initializing: boolean = false;
  private _initPromise: Promise<void> = Promise.resolve();

  constructor() {
    this._chainSlug = ConfigManager.config.SOLANA_CHAIN

    if(ConfigManager.config.SOLANA_CUSTOM_RPC == null) {
      switch (this._chainSlug) {
        case 'mainnet-beta':
          this.rpcUrl = 'https://mainnet.infura.io/v3/'
          break;
        case 'devnet':
          this.rpcUrl = 'https://api.devnet.solana.com'
          break;
        case 'testnet':
          this.rpcUrl = 'https://api.testnet.solana.com'
          break;
        default:
          throw new Error('SOLANA_CHAIN not valid')
      }
    }
    else
    {
      this.rpcUrl = ConfigManager.config.SOLANA_CUSTOM_RPC
    }

    this._connection = new Connection(this.rpcUrl, "processed" as Commitment)
    this.cache = new NodeCache({ stdTTL: 3600 }) // set default cache ttl to 1hr

    this._nativeTokenSymbol = 'SOL'
    this._tokenProgramAddress = new PublicKey(ConfigManager.config.SOLANA_TOKEN_PROGRAM)

    this.transactionLamports = ConfigManager.config.SOLANA_TRANSACTION_LAMPORTS
    this._lamportPrice = ConfigManager.config.SOLANA_LAMPORTS_TO_SOL
    this._lamportDecimals = countDecimals(this._lamportPrice)

    this._requestCount = 0
    this._metricsLogInterval = 300000 // 5 minutes

    this.onDebugMessage('all', this.requestCounter.bind(this))
    setInterval(this.metricLogger.bind(this), this.metricsLogInterval)
  }

  public static getInstance(): Solana {
    if (!Solana._instance) {
      Solana._instance = new Solana()
    }

    return Solana._instance
  }

  public static reload(): Solana {
    Solana._instance = new Solana()
    return Solana._instance
  }

  ready(): boolean {
    return this._ready
  }

  public get connection() {
    return this._connection
  }

  public onNewSlot(func: SlotUpdateCallback) {
    this._connection.onSlotUpdate(func)
  }

  public onDebugMessage(filter: LogsFilter, func: LogsCallback) {
    this._connection.onLogs(filter, func)
  }

  async init(): Promise<void> {
    if (!this.ready() && !this._initializing) {
      this._initializing = true
      this._initPromise = this.loadTokens().then(() => {
        this._ready = true
        this._initializing = false
      })
    }
    return this._initPromise
  }

  async loadTokens(): Promise<void> {
    this.tokenList = await this.getTokenList();
    this.tokenList.forEach(
      (token: TokenInfo) => (this._tokenMap[token.symbol] = token)
    )
  }

  // returns a Tokens for a given list source and list type
  async getTokenList(): Promise<TokenInfo[]> {
    const tokens = await new TokenListProvider().resolve()
    return tokens.filterByClusterSlug(this._chainSlug).getList()
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

  // returns Keypair for a private key, which should be encoded in Base58
  getWallet(privateKey: string): Keypair {
    const decoded = bs58.decode(privateKey);
    if (decoded.length != 32) {
      throw new Error(`Invalid public key input`);
    }
    return Keypair.fromSecretKey(decoded);
  }

  // returns the SOL balance, convert BigNumber to string
  async getSolBalance(wallet: Keypair): Promise<TokenValue> {
    const lamports = await this.connection.getBalance(wallet.publicKey);
    return {value: BigNumber.from(lamports), decimals: this._lamportDecimals}
  }

  tokenResponseToTokenValue(account: TokenAmount): TokenValue {
    return { value: BigNumber.from(account.amount), decimals: account.decimals };
  }

  // returns the balance for an SPL token
  async getSplBalance(
    wallet: Keypair,
    mintAddress: PublicKey
  ): Promise<TokenValue> {
    const response = await this.connection.getParsedTokenAccountsByOwner(wallet.publicKey, {mint: mintAddress});
    if(response['value'].length == 0) {
      throw new Error(`Token account not initialized`);
    }
    return this.tokenResponseToTokenValue(response.value[0].account.data.parsed['info']['tokenAmount']);
  }

  // returns whether the token account is initialized
  async isTokenAccountInitialized(
    wallet: Keypair,
    tokenAddress: PublicKey
  ): Promise<boolean> {
    const tokenProgram = new TokenProgram(this._connection, tokenAddress, this._tokenProgramAddress, wallet)
    try {
      await tokenProgram.getAccountInfo(tokenAddress)
    } catch (err: any) {
      if (err.message === 'Failed to find account' || err.message === 'Invalid account owner')
        return false
      else
        throw err
    }
    return true
  }

  // adds token account to signing wallet, to be able to receive tokens
  async initializeTokenAccount(wallet: Keypair, tokenAddress: PublicKey): Promise<PublicKey> {
    const tokenProgram = new TokenProgram(this._connection, tokenAddress, this._tokenProgramAddress, wallet)
    return await tokenProgram.createAssociatedTokenAccount(wallet.publicKey)
  }

  // returns an ethereum TransactionResponse for a txHash.
  async getTransaction(payerSignature: string): Promise<TransactionResponse | null> {
    return this._connection.getTransaction(payerSignature);
  }

  // caches transaction receipt once they arrive
  cacheTransactionReceipt(tx: TransactionResponse) {
    // first (payer) signature is used as cache key since it is unique enough
    this.cache.set(tx.transaction.signatures[0], tx);
  }

  public getTokenBySymbol(tokenSymbol: string): TokenInfo | undefined {
    return this.tokenList.find(
      (token: TokenInfo) => token.symbol.toUpperCase() === tokenSymbol.toUpperCase()
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

  public get chainSlug(): string {
    return this._chainSlug;
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
}
