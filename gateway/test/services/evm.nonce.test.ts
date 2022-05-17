import fs from 'fs';
import fsp from 'fs/promises';
import fse from 'fs-extra';
import os from 'os';
import path from 'path';
import {
  NonceLocalStorage,
  EVMNonceManager,
} from '../../src/services/evm.nonce';
import 'jest-extended';
import { providers } from 'ethers';
import { patch } from './patch';
import { ReferenceCountingCloseable } from '../../src/services/refcounting-closeable';

describe('Test NonceLocalStorage', () => {
  let dbPath: string = '';
  let db: NonceLocalStorage;
  const handle: string = ReferenceCountingCloseable.createHandle();

  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(
      path.join(os.tmpdir(), '/NonceLocalStorage.test.level')
    );
  });

  beforeEach(() => {
    db = NonceLocalStorage.getInstance(dbPath, handle);
  });

  afterAll(async () => {
    await fse.emptyDir(dbPath);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  afterEach(async () => {
    await db.close(handle);
  });

  it('save, get and delete nonces', async () => {
    const testChain1 = 'ethereum';
    const testChain1Id = 1;
    const address1 = 'A';
    const address2 = 'B';

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
    await fs.rmSync(dbPath, { force: true, recursive: true });
  });

  const testChain1 = 'ethereum';
  const testChain1Id = 1;
  // const testChain1Id = 2;
  const testChain2 = 'avalanche';
  const testChain2Id = 1;
  const address1 = 'A';
  // const address1 = 'B';

  it('getNonce reads nonce from node, commits, then reads nonce from memory', async () => {
    const evmNonceManager = new EVMNonceManager(
      testChain1,
      testChain1Id,
      dbPath,
      300
    );

    patch(evmNonceManager, 'mergeNonceFromEVMNode', (_ethAddress: string) => {
      return;
    });

    patch(evmNonceManager, 'getNonceFromNode', (_ethAddress: string) => {
      return Promise.resolve(12);
    });

    await evmNonceManager.init(
      new providers.StaticJsonRpcProvider('https://kovan.infura.io/v3/')
    );

    const nonce = await evmNonceManager.getNonce(address1);

    expect(nonce).toEqual(12);

    await evmNonceManager.commitNonce(address1, nonce);

    const nonce2 = await evmNonceManager.getNonce(address1);

    expect(nonce2).toEqual(13);
  });

  it('commits to the same address on different chains should have separate nonce values', async () => {
    const ethereumNonceManager = new EVMNonceManager(
      testChain1,
      testChain1Id,
      dbPath,
      300
    );

    const avalancheNonceManager = new EVMNonceManager(
      testChain2,
      testChain2Id,
      dbPath,
      300
    );

    patch(
      ethereumNonceManager,
      'mergeNonceFromEVMNode',
      (_ethAddress: string) => {
        return;
      }
    );

    patch(ethereumNonceManager, 'getNonceFromNode', (_ethAddress: string) => {
      return Promise.resolve(30);
    });

    patch(
      avalancheNonceManager,
      'mergeNonceFromEVMNode',
      (_ethAddress: string) => {
        return;
      }
    );

    patch(avalancheNonceManager, 'getNonceFromNode', (_ethAddress: string) => {
      return Promise.resolve(51);
    });

    await ethereumNonceManager.init(new providers.StaticJsonRpcProvider(''));

    await avalancheNonceManager.init(new providers.StaticJsonRpcProvider(''));

    const ethereumNonce1 = await ethereumNonceManager.getNonce(address1);
    const avalancheNonce1 = await avalancheNonceManager.getNonce(address1);

    expect(ethereumNonce1).toEqual(13); // exists from previous test
    expect(avalancheNonce1).toEqual(51);

    await ethereumNonceManager.commitNonce(address1, ethereumNonce1);
    await avalancheNonceManager.commitNonce(address1, avalancheNonce1);

    const ethereumNonce2 = await ethereumNonceManager.getNonce(address1);
    const avalancheNonce2 = await avalancheNonceManager.getNonce(address1);

    expect(ethereumNonce2).toEqual(14);
    expect(avalancheNonce2).toEqual(52);
  });
});
