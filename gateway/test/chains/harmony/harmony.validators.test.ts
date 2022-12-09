import {
  validateAddress,
  invalidAddressError,
  validateSpender,
  invalidSpenderError,
  validateNonce,
  invalidNonceError,
  invalidMaxFeePerGasError,
  validateMaxFeePerGas,
  invalidMaxPriorityFeePerGasError,
  validateMaxPriorityFeePerGas,
} from '../../../src/chains/harmony/harmony.validators';

import { missingParameter } from '../../../src/services/validators';

import 'jest-extended';

describe('validateAddress', () => {
  it('valid when req.address is a address', () => {
    expect(
      validateAddress({
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      })
    ).toEqual([]);
  });

  it('valid when req.address is a bech32 address', () => {
    expect(
      validateAddress({
        address: 'one1l2sjl5gzl6rz8jffn3etq0j9zpljwu44u9889l',
      })
    ).toEqual([]);
  });

  it('return error when req.address does not exist', () => {
    expect(
      validateAddress({
        hello: 'world',
      })
    ).toEqual([missingParameter('address')]);
  });

  it('return error when req.address is invalid', () => {
    expect(
      validateAddress({
        address: 'world',
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

  it("valid when req.spender is a 'sushiswap'", () => {
    expect(
      validateSpender({
        spender: 'sushiswap',
      })
    ).toEqual([]);
  });

  it("valid when req.spender is 'viperswap'", () => {
    expect(
      validateSpender({
        spender: 'viperswap',
      })
    ).toEqual([]);
  });

  it("valid when req.spender is 'defikingdoms'", () => {
    expect(
      validateSpender({
        spender: 'defikingdoms',
      })
    ).toEqual([]);
  });

  it("valid when req.spender is 'defira'", () => {
    expect(
      validateSpender({
        spender: 'defira',
      })
    ).toEqual([]);
  });

  it('return error when req.spender does not exist', () => {
    expect(
      validateSpender({
        hello: 'world',
      })
    ).toEqual([missingParameter('spender')]);
  });

  it('return error when req.spender is invalid', () => {
    expect(
      validateSpender({
        spender: 'world',
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

describe('validateMaxFeePerGas', () => {
  it('valid when req.quote is a string', () => {
    expect(
      validateMaxFeePerGas({
        maxFeePerGas: '5000000000',
      })
    ).toEqual([]);

    expect(
      validateMaxFeePerGas({
        maxFeePerGas: '1',
      })
    ).toEqual([]);
  });

  it('return no error when req.maxFeePerGas does not exist', () => {
    expect(
      validateMaxFeePerGas({
        hello: 'world',
      })
    ).toEqual([]);
  });

  it('return error when req.maxFeePerGas is invalid', () => {
    expect(
      validateMaxFeePerGas({
        maxFeePerGas: 123,
      })
    ).toEqual([invalidMaxFeePerGasError]);
  });
});

describe('validateMaxPriorityFeePerGas', () => {
  it('valid when req.quote is a string', () => {
    expect(
      validateMaxPriorityFeePerGas({
        maxPriorityFeePerGasError: '5000000000',
      })
    ).toEqual([]);

    expect(
      validateMaxPriorityFeePerGas({
        maxPriorityFeePerGasError: '1',
      })
    ).toEqual([]);
  });

  it('return no error when req.maxPriorityFeePerGas does not exist', () => {
    expect(
      validateMaxPriorityFeePerGas({
        hello: 'world',
      })
    ).toEqual([]);
  });

  it('return error when req.maxPriorityFeePerGas is invalid', () => {
    expect(
      validateMaxPriorityFeePerGas({
        maxPriorityFeePerGas: 123,
      })
    ).toEqual([invalidMaxPriorityFeePerGasError]);
  });
});
