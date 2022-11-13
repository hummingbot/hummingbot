import {
  Client,
  Wallet,
  LedgerStream,
  ValidationStream,
  TransactionStream,
  PeerStatusStream,
  ConsensusStream,
  PathFindStream,
} from 'xrpl';
import axios from 'axios';
import { promises as fs } from 'fs';
import crypto from 'crypto';
import fse from 'fs-extra';
import { TokenListType, walletPath } from '../../services/base';
import { ConfigManagerCertPassphrase } from '../../services/config-manager-cert-passphrase';
import { getRippleConfig } from './ripple.config';
import { logger } from '../../services/logger';

export type TrustlineInfo = {
  id: number;
  code: string;
  issuer: string;
  title: string;
  trustlines: number;
  placeInTop: null;
};

export type TokenBalance = {
  currency: string;
  issuer?: string;
  value: string;
};

export class Ripple implements Rippleish {
  private static _instances: { [name: string]: Ripple };
  public rpcUrl;

  protected tokenList: TrustlineInfo[] = [];
  private _tokenMap: Record<string, TrustlineInfo[]> = {};

  private _client: Client;
  private _nativeTokenSymbol: string;
  private _chain: string;
  private _network: string;
  private _requestCount: number;
  private _metricsLogInterval: number;
  private _tokenListSource: string;
  private _tokenListType: TokenListType;

  private _ready: boolean = false;
  private initializing: boolean = false;

  private constructor(network: string) {
    const config = getRippleConfig('ripple', network);

    this._chain = 'ripple';
    this._network = network;
    this.rpcUrl = config.network.nodeUrl;
    this._nativeTokenSymbol = config.network.nativeCurrencySymbol;
    this._tokenListSource = config.network.tokenListSource;
    this._tokenListType = <TokenListType>config.network.tokenListType;

    this._client = new Client(this.rpcUrl, {
      timeout: config.requestTimeout,
      connectionTimeout: config.connectionTimeout,
      feeCushion: config.feeCushion,
      maxFeeXRP: config.maxFeeXRP,
    });

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    this.onValidationReceived(this.requestCounter.bind(this));
    setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
  }

  public static getInstance(network: string): Ripple {
    if (Ripple._instances === undefined) {
      Ripple._instances = {};
    }
    if (!(network in Ripple._instances)) {
      Ripple._instances[network] = new Ripple(network);
    }

    return Ripple._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Ripple } {
    return Ripple._instances;
  }

  public get client() {
    return this._client;
  }

  public onConnected(callback: () => void) {
    this._client.on('connected', callback);
  }

  public onDisconnected(callback: (code: number) => void) {
    this._client.on('disconnected', callback);
  }

  public onLedgerClosed(callback: (ledger: LedgerStream) => void) {
    this._client.on('ledgerClosed', callback);
  }

  public onValidationReceived(
    callback: (validation: ValidationStream) => void
  ) {
    this._client.on('validationReceived', callback);
  }

  public onTransaction(callback: (tx: TransactionStream) => void) {
    this._client.on('transaction', callback);
  }

  public onPeerStatusChange(callback: (status: PeerStatusStream) => void) {
    this._client.on('peerStatusChange', callback);
  }

  public onConsensusPhase(callback: (phase: ConsensusStream) => void) {
    this._client.on('consensusPhase', callback);
  }

  public onPathFind(callback: (path: PathFindStream) => void) {
    this._client.on('path_find', callback);
  }

  public onError(callback: (...err: any[]) => void): void {
    this._client.on('error', callback);
  }

  async init(): Promise<void> {
    if (!this.ready() && !this.initializing) {
      this.initializing = true;
      await this.loadTokens(this._tokenListSource, this._tokenListType);
      this._ready = true;
      this.initializing = false;
    }
  }

  async loadTokens(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<void> {
    this.tokenList = await this.getTokenList(tokenListSource, tokenListType);
    if (this.tokenList) {
      this.tokenList.forEach((token: TrustlineInfo) =>
        this._tokenMap[token.code].push(token)
      );
    }
  }

  async getTokenList(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<TrustlineInfo[]> {
    let tokens;
    if (tokenListType === 'URL') {
      ({
        data: { tokens },
      } = await axios.get(tokenListSource));
    } else {
      ({ tokens } = JSON.parse(await fs.readFile(tokenListSource, 'utf8')));
    }
    return tokens;
  }

  public get storedTokenList(): TrustlineInfo[] {
    return this.tokenList;
  }

  public getTokenForSymbol(code: string): TrustlineInfo[] | null {
    return this._tokenMap[code] ? this._tokenMap[code] : null;
  }

  public getWalletFromSeed(seed: string): Wallet {
    const wallet = Wallet.fromSeed(seed);

    return wallet;
  }

  async getWallet(address: string): Promise<Wallet> {
    const path = `${walletPath}/${this.chain}`;

    const encryptedSeed: string = await fse.readFile(
      `${path}/${address}.json`,
      'utf8'
    );

    const passphrase = ConfigManagerCertPassphrase.readPassphrase();
    if (!passphrase) {
      throw new Error('missing passphrase');
    }
    const decrypted = await this.decrypt(encryptedSeed, passphrase);

    return Wallet.fromSeed(decrypted);
  }

  async encrypt(secret: string, password: string): Promise<string> {
    const algorithm = 'aes-256-ctr';
    const iv = crypto.randomBytes(16);
    const salt = crypto.randomBytes(32);
    const key = crypto.pbkdf2Sync(password, salt, 5000, 32, 'sha512');
    const cipher = crypto.createCipheriv(algorithm, key, iv);
    const encrypted = Buffer.concat([cipher.update(secret), cipher.final()]);

    return JSON.stringify({
      algorithm,
      iv,
      salt,
      encrypted,
    });
  }

  async decrypt(encryptedSecret: string, password: string): Promise<string> {
    const enc = new TextEncoder();
    const hash = JSON.parse(encryptedSecret);
    const salt = enc.encode(hash.salt);
    const key = crypto.pbkdf2Sync(password, salt, 5000, 32, 'sha512');

    console.log(hash);

    const decipher = crypto.createDecipheriv(
      hash.algorithm,
      key,
      enc.encode(hash.iv) // TOFIX: invalid iv
    );

    const decrpyted = Buffer.concat([
      decipher.update(Buffer.from(hash.content, 'hex')),
      decipher.final(),
    ]);

    return decrpyted.toString();
  }

  async getNativeBalance(wallet: Wallet): Promise<string> {
    await this._client.connect();
    const balance = await this._client.getXrpBalance(wallet.address);
    await this._client.disconnect();
    return balance;
  }

  async getAllBalance(wallet: Wallet): Promise<Array<TokenBalance>> {
    await this._client.connect();
    const balances = await this._client.getBalances(wallet.address);
    await this._client.disconnect();
    return balances;
  }

  ready(): boolean {
    return this._ready;
  }

  public get chain(): string {
    return this._chain;
  }

  public get network(): string {
    return this._network;
  }

  public get nativeTokenSymbol(): string {
    return this._nativeTokenSymbol;
  }

  public requestCounter(): void {
    this._requestCount += 1;
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

  public get requestCount(): number {
    return this._requestCount;
  }

  public get metricsLogInterval(): number {
    return this._metricsLogInterval;
  }

  // returns the current block number
  async getCurrentBlockNumber(): Promise<number> {
    await this.client.connect();
    const currentIndex = this.client.getLedgerIndex();
    await this.client.disconnect();
    return currentIndex;
  }

  async close() {
    if (this._network in Ripple._instances) {
      delete Ripple._instances[this._network];
    }
  }
}

export type Rippleish = Ripple;
export const Rippleish = Ripple;
