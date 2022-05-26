import ethers from 'ethers';
import { logger } from './logger';
import { LocalStorage } from './local-storage';
import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from './error-handler';
import { ReferenceCountingCloseable } from './refcounting-closeable';

export class NonceLocalStorage extends ReferenceCountingCloseable {
  private readonly _localStorage: LocalStorage;

  protected constructor(dbPath: string) {
    super(dbPath);
    this._localStorage = LocalStorage.getInstance(dbPath, this.handle);
  }

  public async init(): Promise<void> {
    await this._localStorage.init();
  }

  public async saveNonce(
    chain: string,
    chainId: number,
    address: string,
    nonce: number
  ): Promise<void> {
    return this._localStorage.save(
      chain + '/' + String(chainId) + '/' + address,
      nonce
    );
  }

  public async deleteNonce(
    chain: string,
    chainId: number,
    address: string
  ): Promise<void> {
    return this._localStorage.del(
      chain + '/' + String(chainId) + '/' + address
    );
  }

  public async getNonces(
    chain: string,
    chainId: number
  ): Promise<Record<string, number>> {
    return this._localStorage.get((key: string, value: any) => {
      const splitKey = key.split('/');
      if (
        splitKey.length === 3 &&
        splitKey[0] === chain &&
        splitKey[1] === String(chainId)
      ) {
        return [splitKey[2], parseInt(value)];
      }
      return;
    });
  }

  public async close(handle: string): Promise<void> {
    await super.close(handle);
    if (this.refCount < 1) {
      await this._localStorage.close(this.handle);
    }
  }
}

/**
 * Manages EVM nonce for addresses to ensure logical consistency of nonces when
 * there is a burst of transactions being sent out.
 *
 * This class aims to solve the following problems:
 *
 * 1. Sending multiple EVM transactions concurrently.
 *    Naively, developers would use the transaction count from the EVM node as
 *    the nonce for new transactions. When multiple transactions are being sent
 *    out this way - these transactions would often end up using the same nonce
 *    and thus only one of them would succeed.
 *    The EVM nonce manager ensures the correct serialization of nonces used in
 *    this case, s.t. the nonces for new concurrent transactions will go out as
 *    [n, n+1, n+2, ...] rathan than [n, n, n, ...]
 *
 * 2. Stuck or dropped transactions.
 *    If you've sent out a transaction with nonce n before, but it got stuck or
 *    was dropped from the mem-pool - it's better to just forget about its nonce
 *    and send the next transaction with its nonce rather than to wait for it to
 *    be confirmed.
 *    This is where the `localNonceTTL` parameter comes in. The locally cached
 *    nonces are only remembered for a period of time (default is 5 minutes).
 *    After that, nonce values from the EVM node will be used again to prevent
 *    potentially dropped nonces from blocking new transactions.
 *
 * 3. Canceling, or re-sending past transactions.
 *    Canceling or re-sending past transactions would typically re-use past
 *    nonces. This means the user is intending to reset his transaction chain
 *    back to a certain nonce. The manager should allow the cached nonce to go
 *    back to the specified past nonce when it happens.
 *    This means whenever a transaction is sent with a past nonce or an EVM
 *    cancel happens, the API logic **must** call commitNonce() to reset the
 *    cached nonce back to the specified position.
 */
export class EVMNonceManager extends ReferenceCountingCloseable {
  #addressToNonce: Record<string, [number, Date]> = {};
  #initialized: boolean = false;
  #db: NonceLocalStorage;
  readonly #chainId: number;
  readonly #chainName: string;
  readonly #localNonceTTL: number;

  // this should be private but then we cannot mock it
  public _provider: ethers.providers.Provider | null = null;

  constructor(
    chainName: string,
    chainId: number,
    dbPath: string,
    localNonceTTL: number = 300
  ) {
    const refCountKey: string = `${chainName}/${chainId}/${dbPath}`;
    super(refCountKey);

    this.#chainName = chainName;
    this.#chainId = chainId;
    this.#localNonceTTL = localNonceTTL;
    this.#db = NonceLocalStorage.getInstance(dbPath, this.handle);
  }

  // init can be called many times and generally should always be called
  // getInstance, but it only applies the values the first time it is called
  public async init(provider: ethers.providers.Provider): Promise<void> {
    if (this.#localNonceTTL < 0) {
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE(
          'EVMNonceManager.init delay must be greater than or equal to zero.'
        ),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }

    if (!this._provider) {
      this._provider = provider;
    }

    if (!this.#initialized) {
      await this.#db.init();
      const addressToNonce = await this.#db.getNonces(
        this.#chainName,
        this.#chainId
      );
      for (const [key, value] of Object.entries(addressToNonce)) {
        logger.info(key + ':' + String(value));
        this.#addressToNonce[key] = [value, new Date()];
      }

      await Promise.all(
        Object.keys(this.#addressToNonce).map(async (address) => {
          await this.mergeNonceFromEVMNode(address);
        })
      );
      this.#initialized = true;
    }
  }

  async mergeNonceFromEVMNode(ethAddress: string): Promise<void> {
    if (this._provider !== null) {
      const externalNonce: number = await this._provider.getTransactionCount(
        ethAddress
      );

      this.#addressToNonce[ethAddress] = [externalNonce, new Date()];
      await this.#db.saveNonce(
        this.#chainName,
        this.#chainId,
        ethAddress,
        externalNonce
      );
    } else {
      logger.error(
        'EVMNonceManager.mergeNonceFromEVMNode called before initiated'
      );
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE(
          'EVMNonceManager.mergeNonceFromEVMNode'
        ),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async getNonceFromMemory(ethAddress: string): Promise<number | null> {
    if (this.#initialized) {
      if (this.#addressToNonce[ethAddress]) {
        const timestamp = this.#addressToNonce[ethAddress][1];
        const now = new Date();
        const diffInSeconds = (now.getTime() - timestamp.getTime()) / 1000;
        if (diffInSeconds > this.#localNonceTTL) {
          await this.mergeNonceFromEVMNode(ethAddress);
        }

        return this.#addressToNonce[ethAddress][0];
      } else {
        return null;
      }
    } else {
      logger.error(
        'EVMNonceManager.getNonceFromMemory called before initiated'
      );
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.getNonceFromMemory'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async getNonceFromNode(ethAddress: string): Promise<number> {
    if (this._provider !== null) {
      const nonce: number = await this._provider.getTransactionCount(
        ethAddress
      );

      this.#addressToNonce[ethAddress] = [nonce, new Date()];
      await this.#db.saveNonce(
        this.#chainName,
        this.#chainId,
        ethAddress,
        nonce
      );
      return nonce;
    } else {
      logger.error('EVMNonceManager.getNonceFromNode called before initiated');
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.getNonceFromNode'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async getNonce(ethAddress: string): Promise<number> {
    let nonce: number | null = await this.getNonceFromMemory(ethAddress);
    if (nonce === null) {
      nonce = await this.getNonceFromNode(ethAddress);
    }
    return nonce;
  }

  async commitNonce(
    ethAddress: string,
    txNonce: number | null = null
  ): Promise<void> {
    if (this.#initialized) {
      let newNonce;
      if (txNonce) {
        newNonce = txNonce + 1;
      } else {
        newNonce = (await this.getNonce(ethAddress)) + 1;
      }
      this.#addressToNonce[ethAddress] = [newNonce, new Date()];
      await this.#db.saveNonce(
        this.#chainName,
        this.#chainId,
        ethAddress,
        newNonce
      );
    } else {
      logger.error('EVMNonceManager.commitNonce called before initiated');
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.commitNonce'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async close(ownerHandle: string): Promise<void> {
    await super.close(ownerHandle);
    if (this.refCount < 1) {
      await this.#db.close(this.handle);
    }
  }
}
