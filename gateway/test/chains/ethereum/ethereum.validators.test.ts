import {
  isAddress,
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
} from '../../../src/chains/ethereum/ethereum.validators';

import { missingParameter } from '../../../src/services/validators';

import 'jest-extended';

describe('isAddress', () => {
  it('pass against a well formed public key', () => {
    expect(isAddress('0xFaA12FD102FE8623C9299c72B03E45107F2772B5')).toEqual(
      true
    );
  });

  it('fail against a string that is too short', () => {
    expect(isAddress('0xFaA12FD102FE8623C9299c72')).toEqual(false);
  });

  it('fail against a string that has non-hexadecimal characters', () => {
    expect(isAddress('0xFaA12FD102FE8623C9299c7iwqpneciqwopienff')).toEqual(
      false
    );
  });

  it('fail against a valid public key that is missing the initial 0x', () => {
    expect(isAddress('FaA12FD102FE8623C9299c72B03E45107F2772B5')).toEqual(
      false
    );
  });
});

describe('validateAddress', () => {
  it('valid when req.address is a address', () => {
    expect(
      validateAddress({
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
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

  it("valid when req.spender is a 'uniswap'", () => {
    expect(
      validateSpender({
        spender: 'uniswap',
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
