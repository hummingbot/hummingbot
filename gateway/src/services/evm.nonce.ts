import ethers from 'ethers';
import { logger } from './logger';
import { dbSaveNonce, dbGetChainNonces } from './local-storage';
import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from './error-handler';

export class EVMNonceManager {
  private _addressToNonce: Record<string, [number, Date]> = {};

  private _initialized: boolean = false;
  private _chainId: number;
  private _chainName: string;
  private _delay: number;

  // this should be private but then we cannot mock it
  public _provider: ethers.providers.Provider | null = null;

  constructor(chainName: string, chainId: number, delay: number) {
    this._chainName = chainName;
    this._chainId = chainId;
    this._delay = delay;
  }

  // init can be called many times and generally should always be called
  // getInstance, but it only applies the values the first time it is called
  public async init(provider: ethers.providers.Provider): Promise<void> {
    logger.info('initialize nonce');
    if (!this._provider) {
      this._provider = provider;
    }

    if (!this._initialized) {
      const addressToNonce = await dbGetChainNonces(
        this._chainName,
        this._chainId
      );

      for (const [key, value] of Object.entries(addressToNonce)) {
        logger.info(key + ':' + String(value));
        this._addressToNonce[key] = [value, new Date()];
      }

      await Promise.all(
        Object.keys(this._addressToNonce).map(async (address) => {
          await this.mergeNonceFromEVMNode(address);
        })
      );

      this._initialized = true;
    }

    if (this._delay < 0) {
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE(
          'EVMNonceManager.init delay must be greater than or equal to zero.'
        ),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async mergeNonceFromEVMNode(ethAddress: string): Promise<void> {
    if (this._provider !== null) {
      let internalNonce: number;
      if (this._addressToNonce[ethAddress]) {
        internalNonce = this._addressToNonce[ethAddress][0];
      } else {
        internalNonce = -1;
      }

      const externalNonce: number = await this._provider.getTransactionCount(
        ethAddress
      );

      const newNonce = Math.max(internalNonce, externalNonce);
      this._addressToNonce[ethAddress] = [newNonce, new Date()];
      await dbSaveNonce(this._chainName, this._chainId, ethAddress, newNonce);
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
      if (this._addressToNonce[ethAddress]) {
        const timestamp = this._addressToNonce[ethAddress][1];
        const now = new Date();
        const diffInSeconds = (now.getTime() - timestamp.getTime()) / 1000;
        if (diffInSeconds > this._delay) {
          await this.mergeNonceFromEVMNode(ethAddress);
        }

        return this._addressToNonce[ethAddress][0];
      } else {
        const nonce: number = await this._provider.getTransactionCount(
          ethAddress
        );

        this._addressToNonce[ethAddress] = [nonce, new Date()];
        await dbSaveNonce(this._chainName, this._chainId, ethAddress, nonce);
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
      this._addressToNonce[ethAddress] = [newNonce, new Date()];
      await dbSaveNonce(this._chainName, this._chainId, ethAddress, newNonce);
    } else {
      logger.error('EVMNonceManager.commitNonce called before initiated');
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.commitNonce'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }
}
