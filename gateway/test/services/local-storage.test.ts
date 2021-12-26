import fs from 'fs';
import fsp from 'fs/promises';
import fse from 'fs-extra';
import path from 'path';
import { LocalStorage } from '../../src/services/local-storage';
import 'jest-extended';

describe('Test local-storage', () => {
  let dbPath: string = '';

  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(
      path.join(__dirname, '/local-storage.test.level')
    );
  });

  afterAll(async () => {
    await fse.emptyDir(dbPath);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  it('save, get and delete a key value pair in the local db', async () => {
    const testKey = 'abc';
    const testValue = 123;

    const db = new LocalStorage(dbPath);

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

    // delete the recentley added key/value pair
    await db.del(testKey);

    const results2: Record<string, any> = await db.get((k: string, v: any) => {
      return [k, parseInt(v)];
    });

    // the key has been deleted, expect an empty object
    expect(results2).toStrictEqual({});
  });
});
