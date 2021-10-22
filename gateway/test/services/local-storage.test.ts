import {
  dbDeleteNonce,
  dbSaveNonce,
  dbGetChainNonces,
} from '../../src/services/local-storage';
import 'jest-extended';

describe('Test local-storage', () => {
  it('store with dbSaveNonce and retrieve with dbGetChainNonces', async () => {
    const testChain = 'testchain';
    const testChainId = 123;
    const testAddress = 'testaddress';
    const testValue = 541;

    // clean up any previous db runs
    await dbDeleteNonce(testChain, testChainId, testAddress);

    // saves with a combination of chain/id/address
    await dbSaveNonce(testChain, testChainId, testAddress, testValue);

    const results = await dbGetChainNonces(testChain, testChainId);
    // returns with an address as key, the chain/id is known by the parameters you provide
    expect(results).toEqual({
      [testAddress]: testValue,
    });
  });
});
