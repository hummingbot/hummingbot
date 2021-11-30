import { LocalStorage } from '../../src/services/local-storage';
import 'jest-extended';

describe('Test local-storage', () => {
  it('store with saveNonce and retrieve with getChainNonces', async () => {
    const testChain = 'testchain';
    const testChainId = 123;
    const testAddress = 'testaddress';
    const testValue = 541;

    const dbPath = '/tmp/local-storage.test.level';

    const db = new LocalStorage(dbPath);

    // clean up any previous db runs
    await db.deleteNonce(testChain, testChainId, testAddress);

    // saves with a combination of chain/id/address
    await db.saveNonce(testChain, testChainId, testAddress, testValue);

    const results = await db.getChainNonces(testChain, testChainId);
    // returns with an address as key, the chain/id is known by the parameters you provide
    expect(results).toEqual({
      [testAddress]: testValue,
    });

    expect(db.dbPath).toEqual(dbPath);
  });
});
