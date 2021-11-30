import ethers from 'ethers';
import { logger } from './logger';
import { LocalStorage } from './local-storage';
import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from './error-handler';

export class EVMNonceManager {
  #addressToNonce: Record<string, [number, Date]> = {};

  #initialized: boolean = false;
  #chainId: number;
  #chainName: string;
  #delay: number;
  #db: LocalStorage;

  // this should be private but then we cannot mock it
  public _provider: ethers.providers.Provider | null = null;

  constructor(
    chainName: string,
    chainId: number,
    delay: number,
    dbPath: string = 'gateway.level'
  ) {
    this.#chainName = chainName;
    this.#chainId = chainId;
    this.#delay = delay;
    this.#db = new LocalStorage(dbPath);
  }

  // init can be called many times and generally should always be called
  // getInstance, but it only applies the values the first time it is called
  public async init(provider: ethers.providers.Provider): Promise<void> {
    logger.info('initialize nonce');
    if (this.#delay < 0) {
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
      const addressToNonce = await this.#db.getChainNonces(
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
      let internalNonce: number;
      if (this.#addressToNonce[ethAddress]) {
        internalNonce = this.#addressToNonce[ethAddress][0];
      } else {
        internalNonce = -1;
      }

      const externalNonce: number = await this._provider.getTransactionCount(
        ethAddress
      );

      const newNonce = Math.max(internalNonce, externalNonce);
      this.#addressToNonce[ethAddress] = [newNonce, new Date()];
      await this.#db.saveNonce(
        this.#chainName,
        this.#chainId,
        ethAddress,
        newNonce
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

  async getNonce(ethAddress: string): Promise<number> {
    if (this._provider !== null) {
      if (this.#addressToNonce[ethAddress]) {
        const timestamp = this.#addressToNonce[ethAddress][1];
        const now = new Date();
        const diffInSeconds = (now.getTime() - timestamp.getTime()) / 1000;
        if (diffInSeconds > this.#delay) {
          await this.mergeNonceFromEVMNode(ethAddress);
        }

        return this.#addressToNonce[ethAddress][0];
      } else {
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
      }
    } else {
      logger.error('EVMNonceManager.getNonce called before initiated');
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.getNonce'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async commitNonce(
    ethAddress: string,
    txNonce: number | null = null
  ): Promise<void> {
    if (this._provider !== null) {
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
}
