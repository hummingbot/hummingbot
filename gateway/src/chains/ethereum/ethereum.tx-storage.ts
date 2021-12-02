import { LocalStorage } from '../../services/local-storage';

export class EthTxStorage extends LocalStorage {
  public async saveTx(
    chain: string,
    chainId: number,
    tx: string,
    timestamp: number
  ): Promise<void> {
    return this.save(chain + '/' + String(chainId) + '/' + tx, timestamp);
  }

  public async deleteTx(
    chain: string,
    chainId: number,
    tx: string
  ): Promise<void> {
    return this.del(chain + '/' + String(chainId) + '/' + tx);
  }

  public async getTxs(
    chain: string,
    chainId: number
  ): Promise<Record<string, number>> {
    return this.get((key: string, value: any) => {
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
}

// get posix
// 0xadaef9c4540192e45c991ffe6f12cc86be9c07b80b43487e5778d95c964405c7
// new Date().getTime()
