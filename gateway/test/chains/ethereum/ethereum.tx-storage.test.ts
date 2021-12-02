import { EthTxStorage } from '../../../src/chains/ethereum/ethereum.tx-storage';
import 'jest-extended';

describe('Test local-storage', () => {
  it('save, get and delete a key value pair in the local db', async () => {
    const testChain1 = 'ethereum';
    const testChain1Id = 423;
    const testChain1Tx1 =
      '0xadaef9c4540192e45c991ffe6f12cc86be9c07b80b43487e5778d95c964405c7';
    const testChain1Tx2 =
      '0xadaef9c4540192e45c991ffe6f12cc86be9c07b80b43487edddddddddddddddd';

    const dbPath = '/tmp/ethereum.tx-storage.test.level';

    const db = new EthTxStorage(dbPath);

    // clean up any previous db runs
    await db.deleteTx(testChain1, testChain1Id, testChain1Tx1);

    // saves a key with a value
    const testTimestamp1 = new Date().getTime();
    await db.saveTx(testChain1, testChain1Id, testChain1Tx1, testTimestamp1);

    const results = await db.getTxs(testChain1, testChain1Id);

    // returns with an address as key, the chain/id is known by the parameters you provide
    expect(results).toStrictEqual({
      [testChain1Tx1]: testTimestamp1,
    });

    // store and retrieve a second value for the same chain/chainId
    const testTimestamp2 = new Date().getTime();
    await db.saveTx(testChain1, testChain1Id, testChain1Tx2, testTimestamp2);
    const results2 = await db.getTxs(testChain1, testChain1Id);

    // returns with an address as key, the chain/id is known by the parameters you provide
    expect(results2).toStrictEqual({
      [testChain1Tx1]: testTimestamp1,
      [testChain1Tx2]: testTimestamp2,
    });

    // store and retrieve a third value for the a different chain/chainId
    const testChain2 = 'avalanche';
    const testChain2Id = 10;
    const testChain2Tx1 =
      '0xadaef9c4540192e45c991ffe6f12cc86be9c07b80b43487fffffffffffffffff';
    const testTimestamp3 = new Date().getTime();
    await db.saveTx(testChain2, testChain2Id, testChain2Tx1, testTimestamp3);
    const results3 = await db.getTxs(testChain2, testChain2Id);
    expect(results3).toStrictEqual({
      [testChain2Tx1]: testTimestamp3,
    });

    // test db path is as exected place
    expect(db.dbPath).toStrictEqual(dbPath);

    // delete the recently added key/value pair
    await db.deleteTx(testChain1, testChain1Id, testChain1Tx1);
    await db.deleteTx(testChain1, testChain1Id, testChain1Tx2);

    const results4 = await db.getTxs(testChain1, testChain1Id);

    // the key has been deleted, expect an empty object
    expect(results4).toStrictEqual({});
  });
});
