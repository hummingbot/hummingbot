import {
  Contract,
  providers,
  connect,
  keyStores,
  KeyPair,
  Near,
  transactions,
} from 'near-api-js';
import { createCipheriv, createDecipheriv, randomBytes } from 'crypto';
import axios from 'axios';
import { promises as fs } from 'fs';
import { TokenListType, TokenValue, walletPath } from '../../services/base';
import NodeCache from 'node-cache';
import { EvmTxStorage } from '../../services/evm.tx-storage';
import fse from 'fs-extra';
import { ConfigManagerCertPassphrase } from '../../services/config-manager-cert-passphrase';
import { logger } from '../../services/logger';
import { ReferenceCountingCloseable } from '../../services/refcounting-closeable';
import path from 'path';
import { rootPath } from '../../paths';
import { Account } from 'near-api-js/lib/account';
import { BigNumber } from 'ethers';
import { NodeStatusResult, GasPrice } from 'near-api-js/lib/providers/provider';
import BN from 'bn.js';
import { baseDecode } from 'borsh';

// information about an Near token
export interface TokenInfo {
  chainId: number;
  address: string;
  name: string;
  symbol: string;
  decimals: number;
}

export type NewDebugMsgHandler = (msg: any) => void;

export class NearBase {
  private _provider: providers.JsonRpcProvider;
  protected tokenList: any;
  private _tokenMap: Record<string, TokenInfo> = {};
  // there are async values set in the constructor
  private _ready: boolean = false;
  private _initializing: boolean = false;
  private _initPromise: Promise<void> = Promise.resolve();
  private _keyStore: keyStores.InMemoryKeyStore;
  private _connection: Near | undefined;

  public chainName;
  public network;
  public gasPriceConstant;
  private _gasLimitTransaction;
  public tokenListSource: string;
  public tokenListType: TokenListType;
  public cache: NodeCache;
  public rpcUrl: string;
  private readonly _refCountingHandle: string;
  private readonly _txStorage: EvmTxStorage;

  constructor(
    chainName: string,
    rpcUrl: string,
    network: string,
    tokenListSource: string,
    tokenListType: TokenListType,
    gasPriceConstant: number,
    gasLimitTransaction: number,
    transactionDbPath: string
  ) {
    this._provider = new providers.JsonRpcProvider({ url: rpcUrl });
    this.rpcUrl = rpcUrl;
    this.chainName = chainName;
    this.network = network;
    this.gasPriceConstant = gasPriceConstant;
    this.tokenListSource = tokenListSource;
    this.tokenListType = tokenListType;

    this._refCountingHandle = ReferenceCountingCloseable.createHandle();
    this.cache = new NodeCache({ stdTTL: 3600 }); // set default cache ttl to 1hr
    this._gasLimitTransaction = gasLimitTransaction;
    this._txStorage = EvmTxStorage.getInstance(
      this.resolveDBPath(transactionDbPath),
      this._refCountingHandle
    );
    this._txStorage.declareOwnership(this._refCountingHandle);
    this._keyStore = new keyStores.InMemoryKeyStore();
  }

  ready(): boolean {
    return this._ready;
  }

  public get provider() {
    return this._provider;
  }

  public get gasLimitTransaction() {
    return this._gasLimitTransaction;
  }

  public resolveDBPath(oldPath: string): string {
    if (oldPath.charAt(0) === '/') return oldPath;
    const dbDir: string = path.join(rootPath(), 'db/');
    fse.mkdirSync(dbDir, { recursive: true });
    return path.join(dbDir, oldPath);
  }

  async init(): Promise<void> {
    if (!this.ready() && !this._initializing) {
      this._initializing = true;
      this._connection = await this.connectProvider();
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

  async connectProvider(): Promise<Near> {
    return await connect({
      networkId: this.network,
      keyStore: this._keyStore,
      nodeUrl: this.rpcUrl,
    });
  }

  async loadTokens(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<void> {
    const tokenList = await this.getTokenList(tokenListSource, tokenListType);
    if (tokenList) {
      for (const [key, value] of Object.entries<any>(tokenList)) {
        this._tokenMap[value.symbol] = {
          ...value,
          address: key,
        };
      }
    }
    this.tokenList = Object.values(this._tokenMap);
  }

  // returns a Tokens for a given list source and list type
  async getTokenList(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<any> {
    let data;
    if (tokenListType === 'URL') {
      ({ data } = await axios.get(tokenListSource));
    } else {
      ({ data } = JSON.parse(await fs.readFile(tokenListSource, 'utf8')));
    }
    return data;
  }

  public get txStorage(): EvmTxStorage {
    return this._txStorage;
  }

  public get storedTokenList(): TokenInfo[] {
    return this.tokenList;
  }

  // return the Token object for a symbol
  getTokenForSymbol(symbol: string): TokenInfo | null {
    return this._tokenMap[symbol] ? this._tokenMap[symbol] : null;
  }

  async getWalletFromPrivateKey(
    privateKey: string,
    accountId: string
  ): Promise<Account> {
    if (!this._connection) {
      await this.init();
    }
    // creates a public / private key pair using the provided private key
    const keyPair = KeyPair.fromString(privateKey);

    const accounts = await this._keyStore.getAccounts(this.network);
    if (!accounts.includes(accountId)) {
      // adds the keyPair you created to keyStore
      await this._keyStore.setKey(this.network, accountId, keyPair);
    }
    return <Account>await this._connection?.account(accountId);
  }

  async getWallet(address: string): Promise<Account> {
    const path = `${walletPath}/${this.chainName}`;

    const encryptedPrivateKey: string = await fse.readFile(
      `${path}/${address}.json`,
      'utf8'
    );

    const passphrase = ConfigManagerCertPassphrase.readPassphrase();
    if (!passphrase) {
      throw new Error('missing passphrase');
    }
    const privateKey = this.decrypt(encryptedPrivateKey, passphrase);
    return await this.getWalletFromPrivateKey(privateKey, address);
  }

  encrypt(privateKey: string, password: string): string {
    const iv = randomBytes(16);
    const key = Buffer.alloc(32);
    key.write(password);

    const cipher = createCipheriv('aes-256-cbc', key, iv);

    const encrypted = Buffer.concat([
      cipher.update(privateKey),
      cipher.final(),
    ]);

    return `${iv.toString('hex')}:${encrypted.toString('hex')}`;
  }

  decrypt(encryptedPrivateKey: string, password: string): string {
    const [iv, encryptedKey] = encryptedPrivateKey.split(':');
    const key = Buffer.alloc(32);
    key.write(password);

    const decipher = createDecipheriv(
      'aes-256-cbc',
      key,
      Buffer.from(iv, 'hex')
    );

    const decrpyted = Buffer.concat([
      decipher.update(Buffer.from(encryptedKey, 'hex')),
      decipher.final(),
    ]);

    return decrpyted.toString();
  }

  // returns the Native balance, convert BigNumber to string
  async getNativeBalance(account: Account): Promise<string> {
    return (await account.getAccountBalance()).available;
  }

  // returns the balance for an fungible token
  async getFungibleTokenBalance(contract: Contract | any): Promise<string> {
    logger.info(
      'Requesting balance for owner ' + contract.account.accountId + '.'
    );
    let balance: string;
    try {
      balance = await contract.ft_balance_of({
        account_id: contract.account.accountId,
      });
    } catch (_e) {
      balance = '0';
    }
    logger.info(
      `Raw balance of ${contract.contractId} for ` +
        `${contract.account.accountId}: ${balance}`
    );
    return balance;
  }

  // returns the allowance for an FT (Fungible Token) token
  async getFungibleTokenAllowance(
    _contract: Contract,
    _wallet: keyStores.InMemoryKeyStore,
    _spender: string,
    _decimals: number
  ): Promise<TokenValue> {
    return { value: BigNumber.from('0'), decimals: 0 };
  }

  async getTransaction(
    txHash: string,
    accountId: string
  ): Promise<providers.FinalExecutionOutcome> {
    return await this._provider.txStatus(txHash, accountId);
  }

  // adds allowance by spender to transfer the given amount of Token
  async approveFungibleToken(
    _contract: Contract,
    _wallet: keyStores.InMemoryKeyStore,
    _spender: string,
    _amount: BigNumber
  ): Promise<any> {
    return;
  }

  public getTokenBySymbol(tokenSymbol: string): TokenInfo | undefined {
    return this._tokenMap[tokenSymbol];
  }

  // returns the current block number
  async getCurrentBlockNumber(): Promise<number> {
    const status: NodeStatusResult = await this._provider.status();
    return status.sync_info.latest_block_height;
  }

  // cancel transaction
  async cancelTx(account: Account, nonce: number): Promise<string> {
    const block = await account.connection.provider.block({
      finality: 'final',
    });
    const blockHash = block.header.hash;

    const [txHash, signedTx] = await transactions.signTransaction(
      account.accountId,
      nonce,
      [transactions.transfer(new BN(0))],
      baseDecode(blockHash),
      account.connection.signer,
      account.accountId,
      account.connection.networkId
    );
    await account.connection.provider.sendTransaction(signedTx);

    return txHash.toString();
  }

  /**
   * Get the gas fee.
   */
  async getGasPrice(): Promise<string | null> {
    if (!this.ready) {
      await this.init();
    }
    const feeData: GasPrice = await this._provider.gasPrice(null);
    if (feeData.gas_price !== null) {
      return feeData.gas_price;
    } else {
      return null;
    }
  }

  async close() {
    await this._txStorage.close(this._refCountingHandle);
  }
}
