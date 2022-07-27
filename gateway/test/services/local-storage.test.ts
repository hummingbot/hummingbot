import fs from 'fs';
import fsp from 'fs/promises';
import fse from 'fs-extra';
import os from 'os';
import path from 'path';
import { LocalStorage } from '../../src/services/local-storage';
import 'jest-extended';
import { ReferenceCountingCloseable } from '../../src/services/refcounting-closeable';

let dbPath: string = '';
const handle: string = ReferenceCountingCloseable.createHandle();

beforeAll(async () => {
  dbPath = await fsp.mkdtemp(
    path.join(os.tmpdir(), '/local-storage.test.level')
  );
});

afterAll(async () => {
  await fse.emptyDir(dbPath);
  fs.rmSync(dbPath, { force: true, recursive: true });

  const db: LocalStorage = LocalStorage.getInstance(dbPath, handle);
  await db.close(handle);
});

describe('Test local-storage', () => {
  it('save, get and delete a key value pair in the local db', async () => {
    const testKey = 'abc';
    const testValue = 123;

    const db: LocalStorage = LocalStorage.getInstance(dbPath, handle);

    // clean up any previous db runs
    await db.del(testKey);

    // saves a key with a value
    await db.save(testKey, testValue);

    const results: Record<string, any> = await db.get((k: string, v: any) => {
      return [k, parseInt(v)];
    });

    // returns with an address as key, the chain/id is known by the parameters you provide
    expect(results).toStrictEqual({
      [testKey]: testValue,
    });

    expect(db.dbPath).toStrictEqual(dbPath);

    // delete the recently added key/value pair
    await db.del(testKey);

    const results2: Record<string, any> = await db.get((k: string, v: any) => {
      return [k, parseInt(v)];
    });

    // the key has been deleted, expect an empty object
    expect(results2).toStrictEqual({});
  });

  it('Put and retrieve a objects', async () => {
    const db: LocalStorage = LocalStorage.getInstance(dbPath, handle);

    const firstKey: string = 'camel';
    const firstValue = { kingdom: 'animalia', family: 'camelidae' };

    const secondKey: string = 'elephant';
    const secondValue = { kingdom: 'animalia', family: 'elephantidae' };

    const thirdKey: string = 'trex';
    const thirdValue = { kingdom: 'animalia', family: 'tyrannosauridae' };

    const fourthKey: string = 'shiitake';
    const fourthValue = { kingdom: 'animalia', family: 'omphalotaceae' };

    // saves a key with a value
    await db.save(firstKey, firstValue);
    await db.save(secondKey, secondValue);
    await db.save(thirdKey, thirdValue);
    await db.save(fourthKey, fourthValue);

    const results: Record<string, any> = await db.get((k: string, v: any) => {
      return [k, v];
    });

    expect(results[firstKey]).toStrictEqual(firstValue);
    expect(results[secondKey]).toStrictEqual(secondValue);
    expect(results[thirdKey]).toStrictEqual(thirdValue);
    expect(results[fourthKey]).toStrictEqual(fourthValue);
  });
});
