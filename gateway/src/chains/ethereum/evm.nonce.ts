import ethers from 'ethers';

// provider.getTransactionCount( address [ , blockTag = latest ] ) ⇒ Promise< number > source
// Returns the number of transactions address has ever sent, as of blockTag. This value is required to be the nonce for the next tra// nsaction from address sent to the network.

// nextNonce = Math.max(givenNextNonce, currentNextNonce);

export class EVMNonceManager {
  private _addressToNonce: Record<string, [number, Date]> = {};
  private _provider: ethers.providers.Provider;
  private _delay: number;

  constructor(provider: ethers.providers.Provider, delay: number) {
    this._provider = provider;
    this._delay = delay;
  }

  async mergeNonceFromEVMNode(ethAddress: string): Promise<void> {
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
  }

  async getNonce(ethAddress: string): Promise<number> {
    if (this._addressToNonce[ethAddress]) {
      const timestamp = this._addressToNonce[ethAddress][1];
      const now = new Date();
      const diffInSeconds = (timestamp.getTime() - now.getTime()) / 1000;

      if (diffInSeconds > this._delay) {
        await this.mergeNonceFromEVMNode(ethAddress);
      }

      return this._addressToNonce[ethAddress][0];
    } else {
      const nonce: number = await this._provider.getTransactionCount(
        ethAddress
      );
      this._addressToNonce[ethAddress] = [nonce, new Date()];
      return nonce;
    }
  }

  async commitNonce(
    ethAddress: string,
    txNonce: number | null = null
  ): Promise<void> {
    let newNonce;
    if (txNonce) {
      newNonce = txNonce + 1;
    } else {
      newNonce = (await this.getNonce(ethAddress)) + 1;
    }
    this._addressToNonce[ethAddress] = [newNonce, new Date()];
  }
}
