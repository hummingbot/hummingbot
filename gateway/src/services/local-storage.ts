import { LevelDB } from 'level';
const level = require('level-party');

export class LocalStorage {
  readonly #dbPath: string;
  #db: LevelDB;

  constructor(dbPath: string = 'gateway.level') {
    this.#dbPath = dbPath;
    this.#db = level(dbPath, { createIfMissing: true });
  }

  get dbPath(): string {
    return this.#dbPath;
  }

  async saveNonce(
    chain: string,
    chainId: number,
    address: string,
    nonce: number
  ): Promise<void> {
    return this.#db.put(chain + '/' + String(chainId) + '/' + address, nonce);
  }

  async deleteNonce(
    chain: string,
    chainId: number,
    address: string
  ): Promise<void> {
    return this.#db.del(chain + '/' + String(chainId) + '/' + address);
  }

  async getChainNonces(
    chain: string,
    chainId: number
  ): Promise<Record<string, number>> {
    const stream = this.#db.createReadStream();
    const result = await new Promise<Record<string, number>>(
      (resolve, reject) => {
        const results: Record<string, number> = {};
        stream
          .on('data', ({ key, value }) => {
            const splitKey = key.split('/');
            if (
              splitKey.length === 3 &&
              splitKey[0] === chain &&
              splitKey[1] === String(chainId)
            ) {
              results[splitKey[2]] = parseInt(value);
            }
          })
          .on('error', (err) => {
            reject(err);
          })
          .on('end', () => {
            resolve(results);
          });
      }
    );

    return result;
  }
}
