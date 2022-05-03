import fs from 'fs';
import fsp from 'fs/promises';
import fse from 'fs-extra';
import path from 'path';
import {
  NonceLocalStorage,
  EVMNonceManager,
} from '../../src/services/evm.nonce';
import 'jest-extended';
import { providers } from 'ethers';
import { patch } from './patch';

describe('Test NonceLocalStorage', () => {
  let dbPath: string = '';

  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(
      path.join(__dirname, '/NonceLocalStorage.test.level')
    );
  });

  afterAll(async () => {
    await fse.emptyDir(dbPath);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  it('save, get and delete nonces', async () => {
    const testChain1 = 'ethereum';
    const testChain1Id = 1;
    const address1 = 'A';
    const address2 = 'B';

    const db = NonceLocalStorage.getInstance(dbPath);

    // clean up any previous db runs
    await db.deleteNonce(testChain1, testChain1Id, address1);
    await db.deleteNonce(testChain1, testChain1Id, address2);

    // saves a key with a value
    db.saveNonce(testChain1, testChain1Id, address1, 15);
    db.saveNonce(testChain1, testChain1Id, address2, 23);

    const results = await db.getNonces(testChain1, testChain1Id);

    // returns with an address as key, the chain/id is known by the parameters you provide
    expect(results).toStrictEqual({
      [address1]: 15,
      [address2]: 23,
    });
  });
});

describe('Test EVMNonceManager', () => {
  let dbPath: string = '';

  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(
      path.join(__dirname, '/EVMNonceManager.test.level')
    );
  });

  afterAll(async () => {
    await fse.emptyDir(dbPath);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  it('save, get and delete a key value pair in the local db', async () => {
    const testChain1 = 'ethereum';
    const testChain1Id = 1;
    const address1 = 'A';
    // const address2 = 'B';

    const evmNonceManager = new EVMNonceManager(
      testChain1,
      testChain1Id,
      300,
      dbPath
    );
    patch(evmNonceManager, 'mergeNonceFromEVMNode', (_ethAddress: string) => {
      return; //         return Promise.resolve(return null);
    });
    patch(evmNonceManager, 'getNonceFromNode', (_ethAddress: string) => {
      return Promise.resolve(12);
    });
    await evmNonceManager.init(
      new providers.StaticJsonRpcProvider('https://kovan.infura.io/v3/')
    );

    const nonce = await evmNonceManager.getNonce(address1);

    expect(nonce).toEqual(12);
  });
});
