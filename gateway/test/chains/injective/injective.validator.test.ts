import {
  validateTxHash,
  validateAddress,
  validateAmount,
  validateToken,
  invalidAddressError,
  invalidTxHashError,
  invalidTokenError,
} from '../../../src/chains/injective/injective.validators';

import {
  invalidAmountError,
  missingParameter,
} from '../../../src/services/validators';

import 'jest-extended';

describe('validateTxHash', () => {
  it('valid when req.txHash is a txHash', () => {
    expect(
      validateTxHash({
        txHash:
          '92EE240C1C31E50AAA7E3C00A6280A4BE52E65B5A8A4C1B4A6FEF9E170B14D0F', // noqa: mock
      })
    ).toEqual([]);
  });

  it('return error when req.txHash does not exist', () => {
    expect(
      validateTxHash({
        hello: 'world',
      })
    ).toEqual([missingParameter('txHash')]);
  });

  it('return error when req.txHash is invalid', () => {
    expect(
      validateTxHash({
        txHash: 123,
      })
    ).toEqual([invalidTxHashError]);
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
        address: 123,
      })
    ).toEqual([invalidAddressError]);
  });
});

describe('validateAmount', () => {
  it('valid when req.amount is an amount', () => {
    expect(
      validateAmount({
        amount: '0.2',
      })
    ).toEqual([]);
  });

  it('return error when req.amount does not exist', () => {
    expect(
      validateAmount({
        hello: 'world',
      })
    ).toEqual([missingParameter('amount')]);
  });

  it('return error when req.amount is invalid', () => {
    expect(
      validateAmount({
        amount: 'world',
      })
    ).toEqual([invalidAmountError]);
  });
});

describe('validateToken', () => {
  it('valid when req.token is a token', () => {
    expect(
      validateToken({
        token: 'INJ',
      })
    ).toEqual([]);
  });

  it('return error when req.token does not exist', () => {
    expect(
      validateToken({
        hello: 'world',
      })
    ).toEqual([missingParameter('token')]);
  });

  it('return error when req.token is invalid', () => {
    expect(
      validateToken({
        token: 123,
      })
    ).toEqual([invalidTokenError]);
  });
});
