import { LevelDB } from 'level';
const level = require('level-party');

export class LocalStorage {
  readonly #dbPath: string;
  #db: LevelDB;

  constructor(dbPath: string) {
    this.#dbPath = dbPath;
    this.#db = level(dbPath, { createIfMissing: true });
  }

  get dbPath(): string {
    return this.#dbPath;
  }

  public async save(key: string, value: any): Promise<void> {
    return this.#db.put(key, value);
  }

  public async del(key: string): Promise<void> {
    return this.#db.del(key);
  }

  public async get(
    readFunc: (key: string, string: any) => [string, any] | undefined
  ): Promise<Record<string, any>> {
    const stream = this.#db.createReadStream();
    const result = await new Promise<Record<string, any>>((resolve, reject) => {
      const results: Record<string, any> = {};
      stream
        .on('data', ({ key, value }) => {
          const data = readFunc(key, value);
          if (data) {
            results[data[0]] = data[1];
          }
        })
        .on('error', (err) => {
          reject(err);
        })
        .on('end', () => {
          resolve(results);
        });
    });

    return result;
  }

  public async close(): Promise<void> {
    await this.#db.close();
  }
}
