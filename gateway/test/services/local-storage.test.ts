import { LocalStorage } from '../../src/services/local-storage';
import 'jest-extended';

describe('Test local-storage', () => {
  it('save, get and delete a key value pair in the local db', async () => {
    const testKey = 'abc';
    const testValue = 123;

    const dbPath = '/tmp/local-storage.test.level';

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
