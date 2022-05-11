import fs from 'fs';
import fsp from 'fs/promises';
import path from 'path';

import { patch, unpatch } from '../../services/patch';
import { providers } from 'ethers';
import { EVMNonceManager } from '../../../src/services/evm.nonce';
import {
  InitializationError,
  InvalidNonceError,
  INVALID_NONCE_ERROR_CODE,
  INVALID_NONCE_ERROR_MESSAGE,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../../src/services/error-handler';

import 'jest-extended';

const exampleAddress = '0xFaA12FD102FE8623C9299c72B03E45107F2772B5';

afterEach(() => {
  unpatch();
});

describe('uninitiated EVMNodeService', () => {
  let dbPath = '';
  let nonceManager: EVMNonceManager;
  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(path.join(__dirname, '/evm-nonce1.test.level'));
    nonceManager = new EVMNonceManager('ethereum', 43, 0, 0, dbPath);
  });

  afterAll(async () => {
    await nonceManager.close();
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
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.getNonce'),
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

    const nonceManager2 = new EVMNonceManager('ethereum', 43, -5, 0, dbPath);

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
      await nonceManager2.close();
    }
  });

  it('pendingNonceTTL value too low', async () => {
    const provider = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );

    const nonceManager2 = new EVMNonceManager('ethereum', 43, 0, -1, dbPath);

    try {
      await expect(nonceManager2.init(provider)).rejects.toThrow(
        new InitializationError(
          SERVICE_UNITIALIZED_ERROR_MESSAGE(
            'EVMNonceManager.init pendingNonceTTL must be greate than or equal to zero.'
          ),
          SERVICE_UNITIALIZED_ERROR_CODE
        )
      );
    } finally {
      await nonceManager2.close();
    }
  });
});

describe('EVMNodeService', () => {
  let nonceManager: EVMNonceManager;
  let dbPath = '';
  const provider = new providers.StaticJsonRpcProvider(
    'https://ethereum.node.com'
  );

  beforeEach(async () => {
    dbPath = await fsp.mkdtemp(path.join(__dirname, '/evm-nonce2.test.level'));
    nonceManager = new EVMNonceManager('ethereum', 43, 0, 0, dbPath);
    await nonceManager.init(provider);
    await nonceManager.commitNonce(exampleAddress, 0);
  });

  afterAll(async () => {
    await nonceManager.close();
    fs.rmSync(dbPath, { force: true, recursive: true });
  });
  const patchGetTransactionCount = () => {
    if (nonceManager._provider) {
      patch(nonceManager._provider, 'getTransactionCount', () => 11);
    }
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

    await nonceManager.mergeNonceFromEVMNode(exampleAddress);
    const nonce = await nonceManager.getNonce(exampleAddress);
    await expect(nonce).toEqual(19);
  });

  it('getNextNonce should return nonces that are sequentially increasing', async () => {
    // Prevents nonce from expiring.
    patchGetTransactionCount();
    patch(nonceManager, '_pendingNonceTTL', () => 300 * 1000);
    nonceManager.commitNonce(exampleAddress, 1);

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

    const pendingNonce2 = await nonceManager.getNextNonce(exampleAddress);
    expect(pendingNonce2).toEqual(pendingNonce1);
  });
});

describe("EVMNodeService was previously a singleton. Let's prove that it no longer is.", () => {
  let nonceManager1: EVMNonceManager;
  let nonceManager2: EVMNonceManager;
  let dbPath = '';
  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(path.join(__dirname, '/evm-nonce3.test.level'));
    nonceManager1 = new EVMNonceManager('ethereum', 43, 60, 60, dbPath);
    const provider1 = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );
    await nonceManager1.init(provider1);

    nonceManager2 = new EVMNonceManager('avalanche', 56, 60, 60, dbPath);
    const provider2 = new providers.StaticJsonRpcProvider(
      'https://avalanche.node.com'
    );
    await nonceManager2.init(provider2);
  });

  afterAll(async () => {
    await nonceManager1.close();
    await nonceManager2.close();
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  it('commitNonce with a provided txNonce will only update current nonce if txNonce > currentNonce', async () => {
    if (nonceManager1._provider) {
      patch(nonceManager1._provider, 'getTransactionCount', () => 1);
    }
    await nonceManager1.commitNonce(exampleAddress, 10);
    const nonce1 = await nonceManager1.getNonce(exampleAddress);
    await expect(nonce1).toEqual(10);

    if (nonceManager1._provider) {
      patch(nonceManager1._provider, 'getTransactionCount', () => 8);
    }
    await nonceManager1.commitNonce(exampleAddress, 8);
    const nonce2 = await nonceManager1.getNonce(exampleAddress);
    await expect(nonce2).toEqual(10);
  });
});
