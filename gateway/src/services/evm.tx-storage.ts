import { LocalStorage } from './local-storage';

// store the timestamp for when a transaction was initiated
// this will be used to calculate a heuristic of the likelihood
// a mempool transaction will be included in a future block
export class EvmTxStorage extends LocalStorage {
  // pass in a date, then store it as a POSIX timestamp
  public async saveTx(
    chain: string,
    chainId: number,
    tx: string,
    date: Date,
    currentGasPrice: number
  ): Promise<void> {
    return this.save(
      chain + '/' + String(chainId) + '/' + tx,
      date.getTime().toString() + ',' + currentGasPrice.toString()
    );
  }

  public async deleteTx(
    chain: string,
    chainId: number,
    tx: string
  ): Promise<void> {
    return this.del(chain + '/' + String(chainId) + '/' + tx);
  }

  // retrieve POSIX timestamps and convert them back into JavaScript Date types
  public async getTxs(
    chain: string,
    chainId: number
  ): Promise<Record<string, [Date, number]>> {
    return this.get((key: string, value: string) => {
      const splitKey = key.split('/');
      const splitValue = value.split(',');
      if (
        splitKey.length === 3 &&
        splitKey[0] === chain &&
        splitKey[1] === String(chainId) &&
        splitValue.length === 2
      ) {
        return [
          splitKey[2],
          [new Date(parseInt(splitValue[0])), parseInt(splitValue[1])],
        ];
      }
      return;
    });
  }
}
