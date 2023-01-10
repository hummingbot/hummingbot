import {
  HttpException,
  AMOUNT_NOT_SUPPORTED_ERROR_CODE,
  AMOUNT_NOT_SUPPORTED_ERROR_MESSAGE,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
} from '../../services/error-handler';
import {
  chainIdToInt,
  getChainIdFromString,
  getNetworkFromString,
  networkToString,
} from './injective.mappers';
import { ReferenceCountingCloseable } from '../../services/refcounting-closeable';
import { BigNumber } from 'ethers';
import {
  bigNumberWithDecimalToStr,
  floatStringWithDecimalToBigNumber,
} from '../../services/base';
import { logger } from '../../services/logger';
import { Wallet as EthereumWallet } from 'ethers';
import { walletPath } from '../../services/base';
import fse from 'fs-extra';
import { ConfigManagerCertPassphrase } from '../../services/config-manager-cert-passphrase';
import { ChainId } from '@injectivelabs/ts-types';
import {
  BaseAccount,
  Denom,
  MsgDeposit,
  MsgWithdraw,
  ChainRestAuthApi,
  ChainRestBankApi,
  IndexerGrpcAccountApi,
  IndexerGrpcSpotApi,
  PrivateKey,
  SubaccountBalance,
  TxRestClient,
  ChainRestTendermintApi,
} from '@injectivelabs/sdk-ts';
import { Network, getNetworkEndpoints } from '@injectivelabs/networks';
import { getInjectiveConfig } from './injective.config';
import {
  BankBalance,
  BalancesResponse,
  SubaccountBalanceSub,
  SubaccountBalancesWithId,
} from './injective.requests';
import { EVMNonceManager } from '../../services/evm.nonce';
import {
  ConfigManagerV2,
  resolveDBPath,
} from '../../services/config-manager-v2';
import { MsgBroadcasterLocal } from './injective.message';
import { AccountDetails } from '@injectivelabs/sdk-ts/dist/types/auth';
import LRUCache from 'lru-cache';
import { TokenInfo } from '../../services/base';

export interface InjectiveWallet {
  ethereumAddress: string;
  injectiveAddress: string;
  privateKey: string;
  subaccountId: string;
}

export class Injective {
  private static _instances: LRUCache<string, Injective>;
  private _ready: boolean = false;
  private _initializing: boolean = false;

  private _network: Network;
  private _chainId: ChainId;
  private _chainName: string = 'injective';
  private _endpoints;
  private _denomToToken: Record<string, TokenInfo> = {}; // the addresses are prefixed with things like peggy, ibc, etc. They come from the injective api.

  private _symbolToToken: Record<string, TokenInfo> = {};
  private _spotApi: IndexerGrpcSpotApi;
  private _indexerGrpcAccountApi: IndexerGrpcAccountApi;
  private _chainRestTendermintApi: ChainRestTendermintApi;
  private _chainRestAuthApi: ChainRestAuthApi;
  private _chainRestBankApi: ChainRestBankApi;

  private readonly _refCountingHandle: string;
  private readonly _nonceManager: EVMNonceManager;

  public gasPrice = 500000000;
  public nativeTokenSymbol = 'INJ';
  public currentBlock = 0;
  public maxCacheSize: number;
  private _blockUpdateIntervalID: number | undefined;
  private _walletMap: LRUCache<string, InjectiveWallet>;

  private constructor(network: Network, chainId: ChainId) {
    this._network = network;
    this._chainId = chainId;
    this._endpoints = getNetworkEndpoints(this._network);
    logger.info(`Injective endpoints: ${JSON.stringify(this._endpoints)}`);
    this._spotApi = new IndexerGrpcSpotApi(this._endpoints.indexer);
    this._indexerGrpcAccountApi = new IndexerGrpcAccountApi(
      this._endpoints.indexer
    );
    this._chainRestTendermintApi = new ChainRestTendermintApi(
      <string>this._endpoints.rest
    );
    this._chainRestAuthApi = new ChainRestAuthApi(this._endpoints.rest);
    this._chainRestBankApi = new ChainRestBankApi(this._endpoints.rest);

    this._refCountingHandle = ReferenceCountingCloseable.createHandle();
    this._nonceManager = new EVMNonceManager(
      'injective',
      chainIdToInt(this._chainId),
      resolveDBPath(
        ConfigManagerV2.getInstance().get('database.transactionDbPath')
      ),
      60000,
      60000
    );
    const config = getInjectiveConfig(networkToString(network));
    this.maxCacheSize = config.network.maxLRUCacheInstances;
    this._nonceManager.declareOwnership(this._refCountingHandle);
    this._walletMap = new LRUCache<string, InjectiveWallet>({
      max: this.maxCacheSize,
    });
  }

  public static getInstance(networkStr: string): Injective {
    if (Injective._instances === undefined) {
      const config = getInjectiveConfig(networkStr);
      Injective._instances = new LRUCache<string, Injective>({
        max: config.network.maxLRUCacheInstances,
      });
    }

    if (!Injective._instances.has(networkStr)) {
      const config = getInjectiveConfig(networkStr);
      const network = getNetworkFromString(networkStr);
      const chainId = getChainIdFromString(config.network.chainId);
      if (network !== null && chainId !== null) {
        Injective._instances.set(networkStr, new Injective(network, chainId));
      } else {
        throw new Error(
          `Injective.getInstance received an unexpected network: ${network}.`
        );
      }
    }

    return Injective._instances.get(networkStr) as Injective;
  }

  public async init(): Promise<void> {
    if (!this.ready() && !this._initializing) {
      this._initializing = true;
      // initialize nonce manager
      await this._nonceManager.init(
        async (address) => await this.getTransactionCount(address)
      );
      // start updating block number
      this._blockUpdateIntervalID = setInterval(async () => {
        await this.updateCurrentBlockNumber();
      }, 2000) as unknown as number;

      // get tokens
      const rawMarkets = await this._spotApi.fetchMarkets();
      for (const market of rawMarkets) {
        if (market.baseToken) {
          const token = {
            address: market.baseToken.address ? market.baseToken.address : '',
            chainId: chainIdToInt(this._chainId),
            name: market.baseToken.name,
            decimals: market.baseToken.decimals,
            symbol: market.baseToken.symbol,
            denom: market.baseDenom,
          };
          this._symbolToToken[market.baseToken.symbol] = token;
          this._denomToToken[market.baseDenom] = token;
        }

        if (market.quoteToken) {
          const token = {
            address: market.quoteToken.address ? market.quoteToken.address : '',
            chainId: chainIdToInt(this._chainId),
            name: market.quoteToken.name,
            decimals: market.quoteToken.decimals,
            symbol: market.quoteToken.symbol,
            denom: market.quoteDenom,
          };
          this._symbolToToken[market.quoteToken.symbol] = token;
          this._denomToToken[market.quoteDenom] = token;
        }
        this._ready = true;
        this._initializing = false;
      }
    }
    return;
  }

  public get chainRestTendermintApi(): ChainRestTendermintApi {
    return this._chainRestTendermintApi;
  }

  public get chainRestBankApi(): ChainRestBankApi {
    return this._chainRestBankApi;
  }

  public ready(): boolean {
    return this._ready;
  }

  public get network(): string {
    return this._network;
  }

  public get chainId(): ChainId {
    return this._chainId;
  }

  public get chainName(): string {
    return this._chainName;
  }

  public get endpoints() {
    return this._endpoints;
  }

  public get nonceManager() {
    return this._nonceManager;
  }

  public get storedTokenList(): Array<TokenInfo> {
    return Object.values(this._symbolToToken);
  }

  public static getConnectedInstances(): { [name: string]: Injective } {
    const connectedInstances: { [name: string]: Injective } = {};
    if (this._instances !== undefined) {
      for (const instance of this._instances.keys()) {
        connectedInstances[instance] = this._instances.get(
          instance
        ) as Injective;
      }
    }
    return connectedInstances;
  }

  public broadcaster(privateKey: string) {
    return MsgBroadcasterLocal.getInstance({
      network: this._network,
      privateKey,
    });
  }

  public async currentBlockNumber(): Promise<number> {
    return Number(
      (await this._chainRestTendermintApi.fetchLatestBlock()).header.height
    );
  }

  public async updateCurrentBlockNumber() {
    this.currentBlock = await this.currentBlockNumber();
  }

  public async poll(txHash: string): Promise<any> {
    return await new TxRestClient(this.endpoints.rest).fetchTx(txHash);
  }

  private getPrivateKeyFromHex(privateKey: string): PrivateKey {
    return PrivateKey.fromHex(privateKey);
  }

  public getWalletFromPrivateKey(privateKey: string): EthereumWallet {
    return new EthereumWallet(privateKey);
  }

  public encrypt(privateKey: string, password: string): Promise<string> {
    const wallet = this.getWalletFromPrivateKey(privateKey);
    return wallet.encrypt(password);
  }

  private async decrypt(
    encryptedPrivateKey: string,
    password: string
  ): Promise<EthereumWallet> {
    return EthereumWallet.fromEncryptedJson(encryptedPrivateKey, password);
  }

  // getWallet by subsaccountid
  public async getWallet(address: string): Promise<InjectiveWallet> {
    if (!this._walletMap.has(address)) {
      this._walletMap.set(address, await this.loadWallet(address));
    }
    return this._walletMap.get(address) as InjectiveWallet;
  }

  private async loadWallet(address: string): Promise<InjectiveWallet> {
    const path = `${walletPath}/${this._chainName}`;

    const encryptedPrivateKey: string = await fse.readFile(
      `${path}/${address}.json`,
      'utf8'
    );

    const passphrase = ConfigManagerCertPassphrase.readPassphrase();
    if (!passphrase) {
      throw new Error('missing passphrase');
    }
    const ethereumWallet = await this.decrypt(encryptedPrivateKey, passphrase);
    const privateKey = this.getPrivateKeyFromHex(ethereumWallet.privateKey);
    const ethereumAddress = privateKey.toHex();

    return {
      privateKey: ethereumWallet.privateKey,
      injectiveAddress: privateKey.toBech32(),
      ethereumAddress,
      subaccountId: address,
    };
  }

  public async transferToSubAccount(
    wallet: InjectiveWallet,
    amount: string, // string encoded float, this needs to be resolved as an integer string
    tokenSymbol: string // the token symbol, this needs to be resolved as the denom
  ): Promise<string> {
    const denom = this.getTokenForSymbol(tokenSymbol);

    if (denom && denom.denom) {
      const correctAmount = floatStringWithDecimalToBigNumber(
        amount,
        denom.decimals
      );
      if (correctAmount === null) {
        throw new HttpException(
          500,
          AMOUNT_NOT_SUPPORTED_ERROR_MESSAGE,
          AMOUNT_NOT_SUPPORTED_ERROR_CODE
        );
      }
      const amountPair = {
        amount: correctAmount.toString(),
        denom: denom.denom,
      };
      const msg = MsgDeposit.fromJSON({
        amount: amountPair,
        subaccountId: wallet.subaccountId,
        injectiveAddress: wallet.injectiveAddress,
      });

      const response = await this.broadcaster(wallet.privateKey).broadcast({
        msgs: msg,
        injectiveAddress: wallet.injectiveAddress,
      });
      return response.txHash;
    } else {
      throw new HttpException(
        500,
        TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
        TOKEN_NOT_SUPPORTED_ERROR_CODE
      );
    }
  }

  public async transferToBankAccount(
    wallet: InjectiveWallet,
    amount: string, // string encoded float, this needs to be resolved as an integer string
    tokenSymbol: string // the token symbol, this needs to be resolved as the denom
  ): Promise<string> {
    const denom = this.getTokenForSymbol(tokenSymbol);

    if (denom && denom.denom) {
      const correctAmount = floatStringWithDecimalToBigNumber(
        amount,
        denom.decimals
      );
      if (correctAmount === null) {
        throw new HttpException(
          500,
          AMOUNT_NOT_SUPPORTED_ERROR_MESSAGE,
          AMOUNT_NOT_SUPPORTED_ERROR_CODE
        );
      }

      const amountPair = {
        amount: correctAmount.toString(),
        denom: denom.denom,
      };
      const msg = MsgWithdraw.fromJSON({
        amount: amountPair,
        subaccountId: wallet.subaccountId,
        injectiveAddress: wallet.injectiveAddress,
      });

      const response = await this.broadcaster(wallet.privateKey).broadcast({
        msgs: msg,
        injectiveAddress: wallet.injectiveAddress,
      });
      return response.txHash;
    } else {
      throw new HttpException(
        500,
        TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
        TOKEN_NOT_SUPPORTED_ERROR_CODE
      );
    }
  }

  public getTokenForSymbol(symbol: string): TokenInfo | null {
    return this._symbolToToken[symbol] ? this._symbolToToken[symbol] : null;
  }

  async getTokenByDenom(denom: string): Promise<TokenInfo | undefined> {
    if (this._denomToToken[denom] !== undefined) {
      return this._denomToToken[denom];
    } else {
      try {
        const denomToken = await new Denom(
          denom,
          this._network
        ).getDenomToken();
        const token = {
          address: denomToken.address ? denomToken.address : '',
          chainId: chainIdToInt(this._chainId),
          name: denomToken.name,
          decimals: denomToken.decimals,
          symbol: denomToken.symbol,
          denom: denomToken.denom,
        };
        this._denomToToken[denom] = token;
        return token;
      } catch (e) {
        logger.error(
          `Injective did not recognize the token denom: ${denom}`,
          e
        );
        return;
      }
    }
  }

  public async balances(wallet: InjectiveWallet): Promise<BalancesResponse> {
    const bankBalancesRaw = await this._chainRestBankApi.fetchBalances(
      wallet.injectiveAddress
    );
    const bankBalances: Array<BankBalance> = [];
    for (const bankBalance of bankBalancesRaw.balances) {
      const token = await this.getTokenByDenom(bankBalance.denom);
      if (token !== undefined) {
        bankBalances.push({
          token: token.symbol,
          amount: bigNumberWithDecimalToStr(
            BigNumber.from(bankBalance.amount),
            token.decimals
          ),
        });
      }
    }

    const subaccountIds =
      await this._indexerGrpcAccountApi.fetchSubaccountsList(
        wallet.injectiveAddress
      );

    const promises: Array<Promise<Array<SubaccountBalance>>> = [];
    for (const subaccountId of subaccountIds) {
      promises.push(
        this._indexerGrpcAccountApi.fetchSubaccountBalancesList(subaccountId)
      );
    }

    const subaccountData = await Promise.all(promises);

    const subaccounts: Array<SubaccountBalancesWithId> = [];
    for (const subaccountBalances of subaccountData) {
      if (subaccountBalances.length > 0) {
        const balances: Array<SubaccountBalanceSub> = [];
        for (const subaccountBalance of subaccountBalances) {
          if (subaccountBalance.deposit) {
            const token = await this.getTokenByDenom(subaccountBalance.denom);
            if (token !== undefined) {
              const balance: SubaccountBalanceSub = {
                token: token.symbol,

                totalBalance: bigNumberWithDecimalToStr(
                  BigNumber.from(
                    subaccountBalance.deposit.totalBalance.split('.')[0]
                  ),
                  token.decimals
                ),
                availableBalance: bigNumberWithDecimalToStr(
                  BigNumber.from(
                    subaccountBalance.deposit.availableBalance.split('.')[0]
                  ),
                  token.decimals
                ),
              };
              balances.push(balance);
            }
          }
        }
        const subaccount = {
          subaccountId: subaccountBalances[0].subaccountId,
          balances,
        };

        subaccounts.push(subaccount);
      }
    }

    return {
      balances: bankBalances,
      injectiveAddress: wallet.injectiveAddress,
      subaccounts: subaccounts,
    };
  }

  public async getTransactionCount(injectiveAddress: string): Promise<number> {
    const accountDetailsResponse = await this._chainRestAuthApi.fetchAccount(
      injectiveAddress
    );
    const baseAccount = BaseAccount.fromRestApi(accountDetailsResponse);
    const accountDetails = baseAccount.toAccountDetails();

    return accountDetails.sequence;
  }

  public async getOnChainAccount(
    injectiveAddress: string
  ): Promise<AccountDetails> {
    return BaseAccount.fromRestApi(
      await this._chainRestAuthApi.fetchAccount(injectiveAddress)
    ).toAccountDetails();
  }

  // returns the current block number
  async getCurrentBlockNumber(): Promise<number> {
    return await this.currentBlockNumber();
  }

  public async close() {
    const instance = Injective._instances.get(this._network);
    if (instance !== undefined) {
      if (instance._blockUpdateIntervalID !== undefined) {
        clearInterval(instance._blockUpdateIntervalID as number);
      }
      Injective._instances.del(this._network);
    }

    await this._nonceManager.close(this._refCountingHandle);
  }
}
