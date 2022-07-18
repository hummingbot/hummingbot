import { Level } from 'level';
import { ReferenceCountingCloseable } from './refcounting-closeable';

export class LocalStorage extends ReferenceCountingCloseable {
  readonly #dbPath: string;
  #db: Level<string, any>;

  protected constructor(dbPath: string) {
    super(dbPath);
    this.#dbPath = dbPath;
    this.#db = new Level(dbPath, {
      createIfMissing: true,
      valueEncoding: 'json',
    });
  }

  public async init(): Promise<void> {
    await this.#db.open({ passive: true });
  }

  get dbPath(): string {
    return this.#dbPath;
  }

  get dbStatus(): string {
    return this.#db.status;
  }

  private async assertDbOpen(): Promise<void> {
    if (this.#db.status === 'open') {
      // this is the target state, finish!
      return;
    } else if (this.#db.status === 'closing') {
      // do nothing if closing, then try again
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await this.assertDbOpen();
    } else if (this.#db.status === 'closed') {
      // reopen the db
      await this.#db.open({ createIfMissing: true });
      await this.assertDbOpen();
    } else if (this.#db.status === 'opening') {
      // wait for but do not initate the opening of the db
      await this.#db.open({ passive: true });
    }
  }

  public async save(key: string, value: any): Promise<void> {
    await this.assertDbOpen();
    await this.#db.put(key, value);
  }

  public async del(key: string): Promise<void> {
    await this.assertDbOpen();
    await this.#db.del(key);
  }

  public async get(
    readFunc: (key: string, string: any) => [string, any] | undefined
  ): Promise<Record<string, any>> {
    await this.assertDbOpen();

    const results: Record<string, any> = {};
    const kvs = await this.#db
      .iterator({
        keys: true,
        values: true,
      })
      .all();
    for (const [key, value] of kvs) {
      const data = readFunc(key, value);
      if (data) {
        results[data[0]] = data[1];
      }
    }

    return results;
  }

  public async close(handle: string): Promise<void> {
    await super.close(handle);
    if (this.refCount < 1) {
      // XXX(martin_kou): `await #db.close()` would freeze. So this is used
      // instead.
      this.#db.close((_) => true);
    }
  }
}
