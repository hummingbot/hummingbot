import ethers from 'ethers';
import { logger } from '../../services/logger';

export class EVMNonceManager {
  private static _instance: EVMNonceManager;
  private _addressToNonce: Record<string, [number, Date]> = {};
  private _provider: ethers.providers.Provider | null = null;
  private _delay: number | null = null;

  private constructor() {}

  public static getInstance(): EVMNonceManager {
    if (!EVMNonceManager._instance) {
      EVMNonceManager._instance = new EVMNonceManager();
    }

    return EVMNonceManager._instance;
  }

  // init can be called many times and generally should always be called
  // getInstance, but it only applies the values the first time it is called
  init(provider: ethers.providers.Provider, delay: number): void {
    if (!this._provider || !this._delay) {
      this._provider = provider;
      this._delay = delay;
    }

    if (delay < 0) {
      throw new Error(
        'EVMNonceManager.init delay must be greater than or equal to zero.'
      );
    }
  }

  async mergeNonceFromEVMNode(ethAddress: string): Promise<void> {
    if (this._provider !== null && this._delay !== null) {
      let internalNonce: number;
      if (this._addressToNonce[ethAddress]) {
        internalNonce = this._addressToNonce[ethAddress][0];
      } else {
        internalNonce = -1;
      }

      const externalNonce: number = await this._provider.getTransactionCount(
        ethAddress
      );

      this._addressToNonce[ethAddress] = [
        Math.max(internalNonce, externalNonce),
        new Date(),
      ];
    } else {
      logger.error(
        'EVMNonceManager.mergeNonceFromEVMNode called before initiated'
      );
      throw new Error(
        'EVMNonceManager.mergeNonceFromEVMNode called before initiated'
      );
    }
  }

  async getNonce(ethAddress: string): Promise<number> {
    if (this._provider !== null && this._delay !== null) {
      if (this._addressToNonce[ethAddress]) {
        const timestamp = this._addressToNonce[ethAddress][1];
        const now = new Date();
        const diffInSeconds = (now.getTime() - timestamp.getTime()) / 1000;

        if (diffInSeconds > this._delay) {
          await this.mergeNonceFromEVMNode(ethAddress);
        }

        return this._addressToNonce[ethAddress][0];
      } else {
        logger.info('getTransactionCount');
        const nonce: number = await this._provider.getTransactionCount(
          ethAddress
        );
        this._addressToNonce[ethAddress] = [nonce, new Date()];
        return nonce;
      }
    } else {
      logger.error('EVMNonceManager.getNonce called before initiated');
      throw new Error('EVMNonceManager.getNonce called before initiated');
    }
  }

  async commitNonce(
    ethAddress: string,
    txNonce: number | null = null
  ): Promise<void> {
    if (this._provider !== null && this._delay !== null) {
      let newNonce;
      if (txNonce) {
        newNonce = txNonce + 1;
      } else {
        newNonce = (await this.getNonce(ethAddress)) + 1;
      }
      this._addressToNonce[ethAddress] = [newNonce, new Date()];
    } else {
      logger.error('EVMNonceManager.commitNonce called before initiated');
      throw new Error('EVMNonceManager.commitNonce called before initiated');
    }
  }
}
