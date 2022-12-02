import fs from 'fs';
import fsp from 'fs/promises';
import os from 'os';
import path from 'path';

import { providers } from 'ethers';
import {
  InitializationError,
  InvalidNonceError,
  INVALID_NONCE_ERROR_CODE,
  INVALID_NONCE_ERROR_MESSAGE,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../../src/services/error-handler';
import { EVMNonceManager } from '../../../src/services/evm.nonce';
import { patch, unpatch } from '../../services/patch';

import 'jest-extended';
import { ReferenceCountingCloseable } from '../../../src/services/refcounting-closeable';

const exampleAddress = '0xFaA12FD102FE8623C9299c72B03E45107F2772B5';

afterEach(() => {
  unpatch();
});

describe('uninitiated EVMNodeService', () => {
  let dbPath = '';
  const handle: string = ReferenceCountingCloseable.createHandle();
  let nonceManager: EVMNonceManager;

  beforeAll(async () => {
    jest.useFakeTimers();
    dbPath = await fsp.mkdtemp(
      path.join(os.tmpdir(), '/evm-nonce1.test.level')
    );
    nonceManager = new EVMNonceManager('ethereum', 43, dbPath, 0, 0);
    nonceManager.declareOwnership(handle);
  });

  afterAll(async () => {
    await nonceManager.close(handle);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  it('mergeNonceFromEVMNode throws error', async () => {
    await expect(
      nonceManager.mergeNonceFromEVMNode(exampleAddress)
    ).rejects.toThrow(
      new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE(
          'EVMNonceManager.mergeNonceFromEVMNode'
        ),
        SERVICE_UNITIALIZED_ERROR_CODE
      )
    );
  });

  it('getNonce throws error', async () => {
    await expect(nonceManager.getNonce(exampleAddress)).rejects.toThrow(
      new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.getNonceFromMemory'),
        SERVICE_UNITIALIZED_ERROR_CODE
      )
    );
  });

  it('commitNonce (txNonce not null) throws error', async () => {
    await expect(nonceManager.commitNonce(exampleAddress, 87)).rejects.toThrow(
      new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.commitNonce'),
        SERVICE_UNITIALIZED_ERROR_CODE
      )
    );
  });

  it('localNonceTTL value too low', async () => {
    const provider = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );

    const nonceManager2 = new EVMNonceManager('ethereum', 43, dbPath, -5, 0);
    nonceManager2.declareOwnership(handle);

    try {
      await expect(nonceManager2.init(provider)).rejects.toThrow(
        new InitializationError(
          SERVICE_UNITIALIZED_ERROR_MESSAGE(
            'EVMNonceManager.init localNonceTTL must be greater than or equal to zero.'
          ),
          SERVICE_UNITIALIZED_ERROR_CODE
        )
      );
    } finally {
      await nonceManager2.close(handle);
    }
  });

  it('pendingNonceTTL value too low', async () => {
    const provider = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );

    const nonceManager2 = new EVMNonceManager('ethereum', 43, dbPath, 0, -5);
    nonceManager2.declareOwnership(handle);

    try {
      await expect(nonceManager2.init(provider)).rejects.toThrow(
        new InitializationError(
          SERVICE_UNITIALIZED_ERROR_MESSAGE(
            'EVMNonceManager.init pendingNonceTTL must be greater than or equal to zero.'
          ),
          SERVICE_UNITIALIZED_ERROR_CODE
        )
      );
    } finally {
      await nonceManager2.close(handle);
    }
  });
});

describe('EVMNodeService', () => {
  let nonceManager: EVMNonceManager;
  let dbPath = '';
  const handle: string = ReferenceCountingCloseable.createHandle();
  const provider = new providers.StaticJsonRpcProvider(
    'https://ethereum.node.com'
  );

  beforeEach(async () => {
    dbPath = await fsp.mkdtemp(
      path.join(os.tmpdir(), '/evm-nonce2.test.level')
    );
    nonceManager = new EVMNonceManager('ethereum', 43, dbPath, 0, 0);
    nonceManager.declareOwnership(handle);
    await nonceManager.init(provider);
    await nonceManager.commitNonce(exampleAddress, 0);
  });

  afterAll(async () => {
    await nonceManager.close(handle);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  const patchGetTransactionCount = () => {
    if (nonceManager._provider) {
      patch(nonceManager._provider, 'getTransactionCount', () => 11);
    }
  };

  const patchDropExpiredPendingNonces = () => {
    patch(nonceManager, 'dropExpiredPendingNonces', (_: any) => {
      return null;
    });
  };

  it('commitNonce with a provided txNonce will only update current nonce if txNonce > currentNonce', async () => {
    patchGetTransactionCount();
    await nonceManager.commitNonce(exampleAddress, 10);
    let nonce = await nonceManager.getNonce(exampleAddress);
    await expect(nonce).toEqual(10);

    await expect(nonceManager.commitNonce(exampleAddress, 5)).rejects.toThrow(
      new InvalidNonceError(
        INVALID_NONCE_ERROR_MESSAGE + `txNonce(5) < currentNonce(10)`,
        INVALID_NONCE_ERROR_CODE
      )
    );

    nonce = await nonceManager.getNonce(exampleAddress);
    await expect(nonce).toEqual(10);
  });

  it('mergeNonceFromEVMNode should update with nonce from EVM node (local<node)', async () => {
    if (nonceManager._provider) {
      patch(nonceManager._provider, 'getTransactionCount', () => 20);
    }

    await nonceManager.commitNonce(exampleAddress, 8);
    jest.advanceTimersByTime(300000);
    await nonceManager.mergeNonceFromEVMNode(exampleAddress);
    const nonce = await nonceManager.getNonce(exampleAddress);
    await expect(nonce).toEqual(19);
  });

  it('getNextNonce should return nonces that are sequentially increasing', async () => {
    // Prevents nonce from expiring.
    patchGetTransactionCount();
    patchDropExpiredPendingNonces();
    patch(nonceManager, '_pendingNonceTTL', 300 * 1000);
    nonceManager.commitNonce(exampleAddress, 1);
    jest.advanceTimersByTime(300000);

    const pendingNonce1 = await nonceManager.getNextNonce(exampleAddress);
    expect(pendingNonce1).toEqual(11);

    const pendingNonce2 = await nonceManager.getNextNonce(exampleAddress);
    expect(pendingNonce2).toEqual(pendingNonce1 + 1);
  });

  it('getNextNonce should reuse expired nonces', async () => {
    // Prevents nonce from expiring.
    patchGetTransactionCount();

    const pendingNonce1 = await nonceManager.getNextNonce(exampleAddress);
    expect(pendingNonce1).toEqual(11);

    // if this runs too quickly it will fail (the nonce has not expired yet)
    jest.advanceTimersByTime(1000);

    const pendingNonce2 = await nonceManager.getNextNonce(exampleAddress);
    expect(pendingNonce2).toEqual(pendingNonce1);

    await nonceManager.commitNonce(exampleAddress, 20);
    jest.advanceTimersByTime(300000);
    await nonceManager.mergeNonceFromEVMNode(exampleAddress);
    const nonce = await nonceManager.getNonce(exampleAddress);
    await expect(nonce).toEqual(10);
  });

  it('provideNonce, nonce not provided. should return function results and commit nonce on successful execution of transaction', async () => {
    // Prevents leading nonce from expiring.
    patchGetTransactionCount();
    patch(nonceManager, '_localNonceTTL', 300 * 1000);

    const testFunction = async (_nonce: number) => {
      return {
        nonce: _nonce,
      };
    };
    const transactionResult = await nonceManager.provideNonce(
      undefined,
      exampleAddress,
      testFunction
    );
    const currentNonceFromMemory = await nonceManager.getNonceFromMemory(
      exampleAddress
    );

    expect(transactionResult.nonce).toEqual(11);
    expect(currentNonceFromMemory).toEqual(11);
  });

  it('provideNonce, nonce not provided. should remove all pendingNonces greater or equal should function fail', async () => {
    // Prevents leading nonce from expiring.
    patchGetTransactionCount();

    const expectedNonce = await nonceManager.getNonceFromMemory(exampleAddress);
    expect(expectedNonce).toEqual(10);

    const pendingNonce1 = await nonceManager.getNextNonce(exampleAddress); // This nonce should expire.
    expect(pendingNonce1).toEqual(11);

    const testFunction = async (_nonce: number) => {
      throw new Error('testFunction has failed.');
    };

    jest.advanceTimersByTime(300000);

    try {
      await nonceManager.provideNonce(undefined, exampleAddress, testFunction);
    } catch (error) {
      expect(error).toEqual(new Error('testFunction has failed.'));
    }

    const currentNonceFromMemory = await nonceManager.getNonceFromMemory(
      exampleAddress
    );

    expect(currentNonceFromMemory).toEqual(expectedNonce);

    const pendingNonce2 = await nonceManager.getNextNonce(exampleAddress);
    expect(pendingNonce2).toEqual(pendingNonce1); // Nonce is re-used.
  });
});

describe("EVMNodeService was previously a singleton. Let's prove that it no longer is.", () => {
  let nonceManager1: EVMNonceManager;
  let nonceManager2: EVMNonceManager;
  let dbPath = '';
  const handle: string = ReferenceCountingCloseable.createHandle();

  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(
      path.join(os.tmpdir(), '/evm-nonce3.test.level')
    );
    nonceManager1 = new EVMNonceManager('ethereum', 43, dbPath, 60, 60);
    const provider1 = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );
    nonceManager1.declareOwnership(handle);
    await nonceManager1.init(provider1);

    nonceManager2 = new EVMNonceManager('avalanche', 56, dbPath, 60, 60);
    nonceManager2.declareOwnership(handle);
    const provider2 = new providers.StaticJsonRpcProvider(
      'https://avalanche.node.com'
    );
    await nonceManager2.init(provider2);
  });

  afterAll(async () => {
    await nonceManager1.close(handle);
    await nonceManager2.close(handle);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  it('commitNonce with a provided txNonce will only update current nonce if txNonce > currentNonce', async () => {
    if (nonceManager1._provider) {
      patch(nonceManager1._provider, 'getTransactionCount', () => 11);
    }
    if (nonceManager2._provider) {
      patch(nonceManager2._provider, 'getTransactionCount', () => 24);
    }

    await nonceManager1.commitNonce(exampleAddress, 10);
    jest.advanceTimersByTime(300000);
    const nonce1 = await nonceManager1.getNonce(exampleAddress);
    await expect(nonce1).toEqual(10);

    await nonceManager2.commitNonce(exampleAddress, 23);
    jest.advanceTimersByTime(300000);
    const nonce2 = await nonceManager2.getNonce(exampleAddress);
    await expect(nonce2).toEqual(23);

    await nonceManager1.commitNonce(exampleAddress, 11);
    jest.advanceTimersByTime(300000);
    const nonce3 = await nonceManager1.getNonce(exampleAddress);
    await expect(nonce3).toEqual(10);
  });
});
