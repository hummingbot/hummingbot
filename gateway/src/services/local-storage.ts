import { Level } from 'level';

export class LocalStorage {
  private static _instances: { [name: string]: LocalStorage };

  readonly #dbPath: string;
  #db: Level<string, any>;

  protected constructor(dbPath: string) {
    this.#dbPath = dbPath;
    // this.#db = new Level(dbPath, { valueEncoding: 'json' });
    this.#db = new Level(dbPath);
  }

  public static getInstance(dbPath: string): LocalStorage {
    if (LocalStorage._instances === undefined) {
      LocalStorage._instances = {};
    }
    if (!(dbPath in LocalStorage._instances)) {
      LocalStorage._instances[dbPath] = new LocalStorage(dbPath);
    }

    return LocalStorage._instances[dbPath];
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
  ): Promise<any> {
    const results: Record<string, any> = {};
    for await (const [key, value] of this.#db.iterator({
      keys: true,
      values: true,
    })) {
      const data = readFunc(key, value);
      if (data) {
        results[data[0]] = data[1];
      }
    }
    return results;
  }

  public async close(): Promise<void> {
    await this.#db.close();
  }
}
