import fs from 'fs';
import fsp from 'fs/promises';
import fse from 'fs-extra';
import os from 'os';
import path from 'path';
import { EvmTxStorage } from '../../src/services/evm.tx-storage';
import 'jest-extended';
import { ReferenceCountingCloseable } from '../../src/services/refcounting-closeable';

describe('Test local-storage', () => {
  let dbPath: string = '';
  let db: EvmTxStorage;
  let handle: string;

  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(
      path.join(os.tmpdir(), '/evm.tx-storage.test.level')
    );
  });

  afterAll(async () => {
    await fse.emptyDir(dbPath);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  beforeEach(() => {
    handle = ReferenceCountingCloseable.createHandle();
    db = EvmTxStorage.getInstance(dbPath, handle);
  });

  afterEach(async () => {
    await db.close(handle);
  });

  it('save, get and delete a key value pair in the local db', async () => {
    const testChain1 = 'ethereum';
    const testChain1Id = 423;
    const testChain1Tx1 =
      '0xadaef9c4540192e45c991ffe6f12cc86be9c07b80b43487e5778d95c964405c7'; // noqa: mock
    const testChain1GasPrice1 = 200000;
    const testChain1Tx2 =
      '0xadaef9c4540192e45c991ffe6f12cc86be9c07b80b43487edddddddddddddddd'; // noqa: mock
    const testChain1GasPrice2 = 200300;

    // clean up any previous db runs
    await db.deleteTx(testChain1, testChain1Id, testChain1Tx1);
    await db.deleteTx(testChain1, testChain1Id, testChain1Tx2);

    // saves a key with a value
    const testTime1 = new Date();
    await db.saveTx(
      testChain1,
      testChain1Id,
      testChain1Tx1,
      testTime1,
      testChain1GasPrice1
    );

    const results = await db.getTxs(testChain1, testChain1Id);

    // returns with an address as key, the chain/id is known by the parameters you provide
    expect(results).toStrictEqual({
      [testChain1Tx1]: [testTime1, testChain1GasPrice1],
    });

    // store and retrieve a second value for the same chain/chainId
    const testTime2 = new Date();
    await db.saveTx(
      testChain1,
      testChain1Id,
      testChain1Tx2,
      testTime2,
      testChain1GasPrice2
    );
    const results2 = await db.getTxs(testChain1, testChain1Id);

    // returns with an address as key, the chain/id is known by the parameters you provide
    expect(results2).toStrictEqual({
      [testChain1Tx1]: [testTime1, testChain1GasPrice1],
      [testChain1Tx2]: [testTime2, testChain1GasPrice2],
    });

    // store and retrieve a third value for the a different chain/chainId
    const testChain2 = 'avalanche';
    const testChain2Id = 10;
    const testChain2Tx1 =
      '0xadaef9c4540192e45c991ffe6f12cc86be9c07b80b43487fffffffffffffffff'; // noqa: mock
    const testChain2GasPrice1 = 4000000;
    const testTime3 = new Date();

    // cleanup from previous test runs
    await db.deleteTx(testChain2, testChain2Id, testChain2Tx1);

    // store data
    await db.saveTx(
      testChain2,
      testChain2Id,
      testChain2Tx1,
      testTime3,
      testChain2GasPrice1
    );

    // retrieve and test
    const results3 = await db.getTxs(testChain2, testChain2Id);
    expect(results3).toStrictEqual({
      [testChain2Tx1]: [testTime3, testChain2GasPrice1],
    });

    // test db path is as exected place
    expect(db.localStorage.dbPath).toStrictEqual(dbPath);

    // delete the recently added key/value pair
    await db.deleteTx(testChain1, testChain1Id, testChain1Tx1);
    await db.deleteTx(testChain1, testChain1Id, testChain1Tx2);

    const results4 = await db.getTxs(testChain1, testChain1Id);

    // the key has been deleted, expect an empty object
    expect(results4).toStrictEqual({});
  });
});
