import { BigNumber } from 'ethers';
import { Harmony } from '../../../src/chains/harmony/harmony';
import { patch, unpatch } from '../../services/patch';
import { TokenInfo } from '../../../src/services/ethereum-base';
import {
  nonce,
  getTokenSymbolsToTokens,
  allowances,
  approve,
  balances,
  cancel,
  willTxSucceed,
} from '../../../src/chains/ethereum/ethereum.controllers';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
} from '../../../src/services/error-handler';
import { patchEVMNonceManager } from '../../evm.nonce.mock';

jest.useFakeTimers();
let harmony: Harmony;

beforeAll(async () => {
  harmony = Harmony.getInstance('testnet');
  patchEVMNonceManager(harmony.nonceManager);
  await harmony.init();
});

beforeEach(() => {
  patchEVMNonceManager(harmony.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await harmony.close();
});

const zeroAddress =
  '0000000000000000000000000000000000000000000000000000000000000000'; // noqa: mock

describe('nonce', () => {
  it('return a nonce for a wallet', async () => {
    patch(harmony, 'getWallet', () => {
      return {
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      };
    });
    patch(harmony.nonceManager, 'getNonce', () => 2);
    const n = await nonce(harmony, {
      chain: 'harmony',
      network: 'testnet',
      address: zeroAddress,
    });
    expect(n).toEqual({ nonce: 2 });
  });
});

const wone: TokenInfo = {
  chainId: 1666700000,
  name: '"Wrapped ONE',
  symbol: 'WONE',
  address: '0x7a2afac38517d512E55C0bCe3b6805c10a04D60F',
  decimals: 18,
};
describe('getTokenSymbolsToTokens', () => {
  it('return tokens for strings', () => {
    patch(harmony, 'getTokenBySymbol', () => {
      return wone;
    });
    expect(getTokenSymbolsToTokens(harmony, ['WONE'])).toEqual({ WONE: wone });
  });
});

const sushiswap = '0x1b02da8cb0d097eb8d57a175b88c7d8b47997506';

describe('allowances', () => {
  it('return allowances for an owner, spender and tokens', async () => {
    patch(harmony, 'getWallet', () => {
      return {
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      };
    });

    patch(harmony, 'getTokenBySymbol', () => {
      return wone;
    });

    patch(harmony, 'getSpender', () => {
      return sushiswap;
    });

    patch(harmony, 'getERC20Allowance', () => {
      return {
        value: BigNumber.from('999999999999999999999999'),
        decimals: 2,
      };
    });

    const result = await allowances(harmony, {
      chain: 'harmony',
      network: 'testnet',
      address: zeroAddress,
      spender: sushiswap,
      tokenSymbols: ['WONE'],
    });
    expect((result as any).approvals).toEqual({
      WONE: '9999999999999999999999.99',
    });
  });
});

describe('approve', () => {
  it('approve a spender for an owner, token and amount', async () => {
    patch(harmony, 'getSpender', () => {
      return sushiswap;
    });
    harmony.getContract = jest.fn().mockReturnValue({
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    });

    patch(harmony, 'ready', () => true);

    patch(harmony, 'getWallet', () => {
      return {
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      };
    });

    patch(harmony, 'getTokenBySymbol', () => {
      return wone;
    });

    patch(harmony, 'approveERC20', () => {
      return {
        spender: sushiswap,
        value: { toString: () => '9999999' },
      };
    });

    const result = await approve(harmony, {
      chain: 'harmony',
      network: 'testnet',
      address: zeroAddress,
      spender: sushiswap,
      token: 'WONE',
    });
    expect((result as any).spender).toEqual(sushiswap);
  });

  it('fail if wallet not found', async () => {
    patch(harmony, 'getSpender', () => {
      return sushiswap;
    });

    const err = 'wallet does not exist';
    patch(harmony, 'getWallet', () => {
      throw new Error(err);
    });

    await expect(
      approve(harmony, {
        chain: 'harmony',
        network: 'testnet',
        address: zeroAddress,
        spender: sushiswap,
        token: 'WONE',
      })
    ).rejects.toThrow(
      new HttpException(
        500,
        LOAD_WALLET_ERROR_MESSAGE + 'Error: ' + err,
        LOAD_WALLET_ERROR_CODE
      )
    );
  });

  it('fail if token not found', async () => {
    patch(harmony, 'getSpender', () => {
      return sushiswap;
    });

    patch(harmony, 'getWallet', () => {
      return {
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      };
    });

    patch(harmony, 'getTokenBySymbol', () => {
      return null;
    });

    await expect(
      approve(harmony, {
        chain: 'harmony',
        network: 'testnet',
        address: zeroAddress,
        spender: sushiswap,
        token: 'WONE',
      })
    ).rejects.toThrow(
      new HttpException(
        500,
        TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + 'WONE',
        TOKEN_NOT_SUPPORTED_ERROR_CODE
      )
    );
  });
});

describe('balances', () => {
  it('fail if wallet not found', async () => {
    const err = 'wallet does not exist';
    patch(harmony, 'getWallet', () => {
      throw new Error(err);
    });

    await expect(
      balances(harmony, {
        chain: 'harmony',
        network: 'testnet',
        address: zeroAddress,
        tokenSymbols: ['WONE', 'WBTC'],
      })
    ).rejects.toThrow(
      new HttpException(
        500,
        LOAD_WALLET_ERROR_MESSAGE + 'Error: ' + err,
        LOAD_WALLET_ERROR_CODE
      )
    );
  });
});

describe('cancel', () => {
  it('fail if wallet not found', async () => {
    const err = 'wallet does not exist';
    patch(harmony, 'getWallet', () => {
      throw new Error(err);
    });

    await expect(
      cancel(harmony, {
        chain: 'harmony',
        network: 'testnet',
        nonce: 123,
        address: zeroAddress,
      })
    ).rejects.toThrow(
      new HttpException(
        500,
        LOAD_WALLET_ERROR_MESSAGE + 'Error: ' + err,
        LOAD_WALLET_ERROR_CODE
      )
    );
  });
});

describe('willTxSucceed', () => {
  it('time limit met and gas price higher than that of the tx', () => {
    expect(willTxSucceed(100, 10, 10, 100)).toEqual(false);
  });

  it('time limit met but gas price has not exceeded that of the tx', () => {
    expect(willTxSucceed(100, 10, 100, 90)).toEqual(true);
  });

  it('time limit not met', () => {
    expect(willTxSucceed(10, 100, 100, 90)).toEqual(true);
  });
});
