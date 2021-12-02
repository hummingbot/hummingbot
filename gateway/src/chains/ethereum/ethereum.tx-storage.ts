import { LocalStorage } from '../../services/local-storage';

// store the timestamp for when a transaction was initiated
// this will be used to calculate a heuristic of the likelihood
// a mempool transaction will be included in a future block
export class EthTxStorage extends LocalStorage {
  // pass in a date, then store it as a POSIX timestamp
  public async saveTx(
    chain: string,
    chainId: number,
    tx: string,
    date: Date
  ): Promise<void> {
    return this.save(chain + '/' + String(chainId) + '/' + tx, date.getTime());
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
  ): Promise<Record<string, Date>> {
    return this.get((key: string, value: any) => {
      const splitKey = key.split('/');
      if (
        splitKey.length === 3 &&
        splitKey[0] === chain &&
        splitKey[1] === String(chainId)
      ) {
        return [splitKey[2], new Date(parseInt(value))];
      }
      return;
    });
  }
}
