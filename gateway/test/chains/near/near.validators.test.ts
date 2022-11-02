import 'jest-extended';
import {
  invalidAddressError,
  invalidChainError,
  invalidNetworkError,
  invalidNonceError,
  invalidSpenderError,
  validateAddress,
  validateBalanceRequest,
  validateChain,
  validateNetwork,
  validateNonce,
  validateSpender,
} from '../../../src/chains/near/near.validators';
import { missingParameter } from '../../../src/services/validators';

export const publicKey = 'test.near';
export const privateKey =
  '5K23ZvkHuNoakyMKGNoaCvky6a2Yu5yfeoRz2wQLKYAczMKzACN5ZZb9ixu6QcsQvrvh91CNfqu8U1LqC1nvnyfp';

describe('validatePublicKey', () => {
  it('valid when req.publicKey is a publicKey', () => {
    expect(
      validateAddress({
        address: publicKey,
      })
    ).toEqual([]);
  });

  it('return error when req.publicKey does not exist', () => {
    expect(
      validateAddress({
        hello: 'world',
      })
    ).toEqual([missingParameter('address')]);
  });

  it('return error when req.publicKey is invalid', () => {
    expect(
      validateAddress({
        address: 1,
      })
    ).toEqual([invalidAddressError]);
  });
});

describe('validateSpender', () => {
  it('valid when req.spender is a publicKey', () => {
    expect(
      validateSpender({
        spender: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      })
    ).toEqual([]);
  });

  it("valid when req.spender is a 'uniswap'", () => {
    expect(
      validateSpender({
        spender: 'uniswap',
      })
    ).toEqual([]);
  });

  it('return error when req.spender is invalid', () => {
    expect(
      validateSpender({
        spender: 123,
      })
    ).toEqual([invalidSpenderError]);
  });
});

describe('validateNonce', () => {
  it('valid when req.nonce is a number', () => {
    expect(
      validateNonce({
        nonce: 0,
      })
    ).toEqual([]);
    expect(
      validateNonce({
        nonce: 999,
      })
    ).toEqual([]);
  });

  it('valid when req.nonce does not exist', () => {
    expect(
      validateNonce({
        hello: 'world',
      })
    ).toEqual([]);
  });

  it('return error when req.nonce is invalid', () => {
    expect(
      validateNonce({
        nonce: '123',
      })
    ).toEqual([invalidNonceError]);
  });
});

describe('validateChain', () => {
  it('invalid when req.chain is a number', () => {
    expect(
      validateChain({
        chain: 2,
      })
    ).toEqual([invalidChainError]);
    expect(
      validateChain({
        chain: 999,
      })
    ).toEqual([invalidChainError]);
  });

  it('valid when req.chain is a string', () => {
    expect(
      validateChain({
        chain: 'world',
      })
    ).toEqual([]);
  });
});

describe('validateNetwork', () => {
  it('invalid when req.network is a number', () => {
    expect(
      validateNetwork({
        network: 2,
      })
    ).toEqual([invalidNetworkError]);
    expect(
      validateNetwork({
        network: 999,
      })
    ).toEqual([invalidNetworkError]);
  });

  it('valid when req.network is a string', () => {
    expect(
      validateNetwork({
        network: 'world',
      })
    ).toEqual([]);
  });
});

describe('validateBalanceRequest', () => {
  it('valid when requests are correct', () => {
    expect(
      validateBalanceRequest({
        address: 'world',
        tokenSymbols: ['token'],
      })
    ).toEqual(undefined);
  });
});
