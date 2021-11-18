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
    nonceManager = EVMNonceManager.getInstance();
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
    nonceManager = EVMNonceManager.getInstance();
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
