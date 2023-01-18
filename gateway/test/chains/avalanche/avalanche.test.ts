jest.useFakeTimers();
import { patch, unpatch } from '../../services/patch';
import { Avalanche } from '../../../src/chains/avalanche/avalanche';
import { patchEVMNonceManager } from '../../evm.nonce.mock';
let avalanche: Avalanche;

// Fake data for for testing
const TOKENS = [
  {
    chainId: 11111,
    address: '0x21cf0eB2E3Ab483a67C900b27dA8F34185991982',
    decimals: 18,
    name: 'Wrapped AVAX',
    symbol: 'WAVAX',
    logoURI:
      'https://raw.githubusercontent.com/pangolindex/tokens/main/assets/11111/0x21cf0eB2E3Ab483a67C900b27dA8F34185991982/logo.png',
  },
  {
    chainId: 43114,
    address: '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
    decimals: 18,
    name: 'Wrapped AVAX',
    symbol: 'WAVAX',
    logoURI:
      'https://raw.githubusercontent.com/pangolindex/tokens/main/assets/0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7/logo.png',
  },
];

beforeAll(async () => {
  avalanche = Avalanche.getInstance('avalanche');
  // Return the mocked token list instead of getting the list from github
  patch(avalanche, 'getTokenList', () => TOKENS);
  patchEVMNonceManager(avalanche.nonceManager);

  await avalanche.init();
});

beforeEach(() => {
  patchEVMNonceManager(avalanche.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await avalanche.close();
});

describe('verify Pangolin storedTokenList', () => {
  it('Should only return tokens in the chain', async () => {
    const tokenList = avalanche.storedTokenList;
    // Only one of them has chainId 43114
    expect(tokenList).toEqual([TOKENS[1]]);
  });
});
