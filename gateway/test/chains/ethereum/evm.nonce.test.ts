import { patch, unpatch } from '../../services/patch';
import { providers } from 'ethers';
import { EVMNonceManager } from '../../../src/services/evm.nonce';
import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../../src/services/error-handler';

import 'jest-extended';

const exampleAddress = '0xFaA12FD102FE8623C9299c72B03E45107F2772B5';

afterEach(() => {
  unpatch();
});

describe('unitiated EVMNodeService', () => {
  let nonceManager: EVMNonceManager;
  beforeAll(() => {
    nonceManager = new EVMNonceManager();
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

  it('commitNonce (txNonce null) throws error', async () => {
    await expect(nonceManager.commitNonce(exampleAddress)).rejects.toThrow(
      new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.commitNonce'),
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
});

describe('EVMNodeService', () => {
  let nonceManager: EVMNonceManager;
  beforeAll(async () => {
    nonceManager = new EVMNonceManager();
    const provider = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );
    await nonceManager.init(provider, 0, 43);
  });

  const patchGetTransactionCount = () => {
    if (nonceManager._provider) {
      patch(nonceManager._provider, 'getTransactionCount', () => 11);
    }
  };

  it('commitNonce with a provided txNonce should increase the nonce by 1', async () => {
    patchGetTransactionCount();
    await nonceManager.commitNonce(exampleAddress, 10);
    const nonce = await nonceManager.getNonce(exampleAddress);

    await expect(nonce).toEqual(11);
  });

  it('mergeNonceFromEVMNode should update with the maximum nonce source (node)', async () => {
    patchGetTransactionCount();

    await nonceManager.commitNonce(exampleAddress, 10);
    await nonceManager.mergeNonceFromEVMNode(exampleAddress);
    const nonce = await nonceManager.getNonce(exampleAddress);
    await expect(nonce).toEqual(11);
  });

  it('mergeNonceFromEVMNode should update with the maximum nonce source (local)', async () => {
    patchGetTransactionCount();

    await nonceManager.commitNonce(exampleAddress, 20);
    await nonceManager.mergeNonceFromEVMNode(exampleAddress);
    const nonce = await nonceManager.getNonce(exampleAddress);
    await expect(nonce).toEqual(21);
  });
});

describe("EVMNodeService was previously a singleton. Let's prove that it no longer is.", () => {
  let nonceManager1: EVMNonceManager;
  let nonceManager2: EVMNonceManager;
  beforeAll(async () => {
    nonceManager1 = new EVMNonceManager();
    const provider1 = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );
    await nonceManager1.init(provider1, 0, 43);

    nonceManager2 = new EVMNonceManager();
    const provider2 = new providers.StaticJsonRpcProvider(
      'https://avalanche.node.com'
    );
    await nonceManager2.init(provider2, 0, 600);
  });

  it('commitNonce with a provided txNonce should increase the nonce by 1', async () => {
    if (nonceManager1._provider) {
      patch(nonceManager1._provider, 'getTransactionCount', () => 1);
    }
    if (nonceManager2._provider) {
      patch(nonceManager2._provider, 'getTransactionCount', () => 13);
    }

    await nonceManager1.commitNonce(exampleAddress, 10);
    const nonce1 = await nonceManager1.getNonce(exampleAddress);
    await expect(nonce1).toEqual(11);

    await nonceManager2.commitNonce(exampleAddress, 23);
    const nonce2 = await nonceManager2.getNonce(exampleAddress);
    await expect(nonce2).toEqual(24);
  });
});
