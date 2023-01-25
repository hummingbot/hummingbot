import { BigNumberInBase, DEFAULT_STD_FEE } from '@injectivelabs/utils';
import {
  PrivateKey,
  Msgs,
  createTransaction,
  getEthereumSignerAddress,
  getInjectiveSignerAddress,
  BroadcastMode,
  TxRestClient,
  TxClient,
} from '@injectivelabs/sdk-ts';
import { EthereumChainId } from '@injectivelabs/ts-types';
import {
  getNetworkEndpoints,
  getNetworkInfo,
  Network,
  NetworkEndpoints,
} from '@injectivelabs/networks';
import { Injective } from './injective';
import { AccountDetails } from '@injectivelabs/sdk-ts/dist/types/auth';
import LRUCache from 'lru-cache';
import { getInjectiveConfig } from './injective.config';
import { networkToString } from './injective.mappers';
import { TxRaw } from '@injectivelabs/chain-api/cosmos/tx/v1beta1/tx_pb';

interface MsgBroadcasterTxOptions {
  msgs: Msgs | Msgs[];
  injectiveAddress: string;
  ethereumAddress?: string;
  memo?: string;
  feePrice?: string;
  feeDenom?: string;
  gasLimit?: number;
  sequence?: number;
}

interface MsgBroadcasterOptionsLocal {
  network: Network;

  /**
   * Only used if we want to override the default
   * endpoints taken from the network param
   */
  endpoints?: {
    indexer: string;
    grpc: string;
    rest: string;
  };
  privateKey: string;
  ethereumChainId?: EthereumChainId;
}

/**
 * This class is used to broadcast transactions
 * using a privateKey as a signer
 * for the transactions and broadcasting
 * the transactions directly to the node
 *
 * Mainly used for working in a Node Environment
 */
export class MsgBroadcasterLocal {
  private _chain: Injective;

  public endpoints: NetworkEndpoints;

  public chainId: string;

  private _privateKey: PrivateKey;

  private _accountDetails: LRUCache<string, AccountDetails>;

  private _localSequence: number;

  private _isBlocked: boolean;

  private _txQueue: MsgBroadcasterTxOptions[];

  private static _instances: LRUCache<string, MsgBroadcasterLocal>;

  constructor(options: MsgBroadcasterOptionsLocal) {
    const networkInfo = getNetworkInfo(options.network);
    const endpoints = getNetworkEndpoints(options.network);

    this.chainId = networkInfo.chainId;
    this.endpoints = { ...endpoints, ...(endpoints || {}) };
    this._chain = Injective.getInstance(options.network);
    this._privateKey = PrivateKey.fromHex(options.privateKey);
    const config = getInjectiveConfig(networkToString(options.network));
    this._accountDetails = new LRUCache<string, AccountDetails>({
      max: config.network.maxLRUCacheInstances,
    });
    this._localSequence = 0;
    this._isBlocked = false;
    this._txQueue = [];
  }

  public static getInstance(
    options: MsgBroadcasterOptionsLocal
  ): MsgBroadcasterLocal {
    if (MsgBroadcasterLocal._instances === undefined) {
      const config = getInjectiveConfig(networkToString(options.network));
      MsgBroadcasterLocal._instances = new LRUCache<
        string,
        MsgBroadcasterLocal
      >({
        max: config.network.maxLRUCacheInstances,
      });
    }
    const instanceKey = options.network + options.privateKey;
    if (!MsgBroadcasterLocal._instances.has(instanceKey)) {
      MsgBroadcasterLocal._instances.set(
        instanceKey,
        new MsgBroadcasterLocal(options)
      );
    }

    return MsgBroadcasterLocal._instances.get(
      instanceKey
    ) as MsgBroadcasterLocal;
  }

  isNextTx(tx: MsgBroadcasterTxOptions): boolean {
    return !this._isBlocked && tx === this._txQueue[0];
  }

  async sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Broadcasting the transaction using the client
   *
   * @param transaction
   * @returns {string} transaction hash
   */
  async broadcast(
    transaction: MsgBroadcasterTxOptions
  ): Promise<{ txHash: string }> {
    let txResponse: {
      data: any;
    };
    const tx = {
      msgs: Array.isArray(transaction.msgs)
        ? transaction.msgs
        : [transaction.msgs],
      ethereumAddress: getEthereumSignerAddress(transaction.injectiveAddress),
      injectiveAddress: getInjectiveSignerAddress(transaction.injectiveAddress),
      sequence: this._localSequence++,
    } as MsgBroadcasterTxOptions;
    this._txQueue.push(tx);

    try {
      while (!this.isNextTx(tx)) {
        await this.sleep(10); // sleep
      }
      this._isBlocked = true;

      /** Account Details **/
      const accountDetails = await this.getAccountDetails(transaction);

      /** Block Details */
      const timeoutHeight = new BigNumberInBase(
        this._chain.currentBlock === 0
          ? await this._chain.currentBlockNumber()
          : this._chain.currentBlock
      ).plus(120);

      /** Prepare the Transaction * */
      const currentNonce = await this._chain.nonceManager.getNextNonce(
        transaction.injectiveAddress
      );
      txResponse = await this.createAndSend(
        tx,
        timeoutHeight,
        accountDetails,
        currentNonce
      );
      if (
        txResponse.data.tx_response.code === 32 &&
        txResponse.data.tx_response.raw_log.startsWith(
          'account sequence mismatch, expected ',
          0
        )
      ) {
        const expectedSequence = Number(
          txResponse.data.tx_response.raw_log
            .split('account sequence mismatch, expected ')[1]
            .split(',')[0]
        );
        await this._chain.nonceManager.overridePendingNonce(
          transaction.injectiveAddress,
          expectedSequence
        );
        txResponse = await this.createAndSend(
          tx,
          timeoutHeight,
          accountDetails,
          expectedSequence
        );
      } else if (txResponse.data.tx_response.code === 0) {
        await this._chain.nonceManager.commitNonce(
          transaction.injectiveAddress,
          currentNonce
        );
      }
    } finally {
      this._txQueue.shift();
      this._isBlocked = false;
    }

    return {
      txHash:
        txResponse.data.tx_response.code === 0
          ? txResponse.data.tx_response.txhash
          : '',
    };
  }

  async createAndSend(
    tx: MsgBroadcasterTxOptions,
    timeoutHeight: BigNumberInBase,
    accountDetails: AccountDetails,
    sequence: number
  ): Promise<{ data: any }> {
    const { signBytes, txRaw } = createTransaction({
      memo: '',
      fee: DEFAULT_STD_FEE,
      message: (tx.msgs as Msgs[]).map((m) => m.toDirectSign()),
      timeoutHeight: timeoutHeight.toNumber(),
      pubKey: this._privateKey.toPublicKey().toBase64(),
      sequence: sequence,
      accountNumber: accountDetails.accountNumber,
      chainId: this.chainId,
    });

    /** Sign transaction */
    const signature = await this._privateKey.sign(Buffer.from(signBytes));

    /** Append Signatures */
    txRaw.setSignaturesList([signature]);
    /** Broadcast transaction */
    const txResponse = await this.broadcastUsingInjective(
      txRaw,
      BroadcastMode.Sync
    );
    return txResponse as { data: any };
  }

  private async broadcastUsingInjective(
    txRaw: TxRaw,
    mode: BroadcastMode
  ): Promise<any> {
    return await new TxRestClient(this.endpoints.rest).httpClient.post<
      URLSearchParams | any,
      { data: any }
    >('cosmos/tx/v1beta1/txs', {
      tx_bytes: TxClient.encode(txRaw),
      mode,
    });
  }

  private async getAccountDetails(
    transaction: MsgBroadcasterTxOptions
  ): Promise<AccountDetails> {
    if (!this._accountDetails.has(transaction.injectiveAddress)) {
      this._accountDetails.set(
        transaction.injectiveAddress,
        await this._chain.getOnChainAccount(transaction.injectiveAddress)
      );
    }
    const accountDetails = this._accountDetails.get(
      transaction.injectiveAddress
    ) as AccountDetails;
    return accountDetails;
  }
}
