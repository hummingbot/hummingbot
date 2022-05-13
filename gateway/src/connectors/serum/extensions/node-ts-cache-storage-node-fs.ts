// eslint-disable-next-line
// @ts-ignore
import * as Bluebird from 'bluebird';
import { ICacheItem, IStorage } from 'node-ts-cache';
import './gserializer';

// eslint-disable-next-line
// @ts-ignore
const serializer = new ONEGEEK.GSerializer();

const Fs = Bluebird.promisifyAll(require('fs'));

export class NodeFsStorage implements IStorage {
  constructor(public jsonFilePath: string) {
    if (!Fs.existsSync(this.jsonFilePath)) {
      this.createEmptyCache();
    }
  }

  public async getItem(key: string): Promise<ICacheItem | undefined> {
    return (await this.getCacheObject())[key];
  }

  public async setItem(key: string, content: any): Promise<void> {
    const cache = await this.getCacheObject();

    cache[key] = content;

    await this.setCache(cache);
  }

  public async clear(): Promise<void> {
    await this.createEmptyCache();
  }

  private createEmptyCache(): void {
    // eslint-disable-next-line
    // @ts-ignore
    Fs.writeFileSync(this.jsonFilePath, serializer.serialize({}));
  }

  private async setCache(newCache: any): Promise<void> {
    await Fs.writeFileAsync(
      this.jsonFilePath,
      // eslint-disable-next-line
      // @ts-ignore
      serializer.serialize(newCache)
    );
  }

  private async getCacheObject(): Promise<any> {
    // eslint-disable-next-line
    // @ts-ignore
    return serializer.deserialize(
      (await Fs.readFileAsync(this.jsonFilePath)).toString()
    );
  }
}
