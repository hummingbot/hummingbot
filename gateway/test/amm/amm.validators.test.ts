import {
  invalidQuoteError,
  validateQuote,
  invalidBaseError,
  validateBase,
  invalidSideError,
  validateSide,
  invalidLimitPriceError,
  validateLimitPrice,
} from '../../src/amm/amm.validators';

import { missingParameter } from '../../src/services/validators';

import 'jest-extended';

describe('validateQuote', () => {
  it('valid when req.quote is a string', () => {
    expect(
      validateQuote({
        quote: 'DAI',
      })
    ).toEqual([]);

    expect(
      validateQuote({
        quote: 'WETH',
      })
    ).toEqual([]);
  });

  it('return error when req.quote does not exist', () => {
    expect(
      validateQuote({
        hello: 'world',
      })
    ).toEqual([missingParameter('quote')]);
  });

  it('return error when req.quote is invalid', () => {
    expect(
      validateQuote({
        quote: 123,
      })
    ).toEqual([invalidQuoteError]);
  });
});

describe('validateBase', () => {
  it('valid when req.base is a string', () => {
    expect(
      validateBase({
        base: 'DAI',
      })
    ).toEqual([]);

    expect(
      validateBase({
        base: 'WETH',
      })
    ).toEqual([]);
  });

  it('return error when req.base does not exist', () => {
    expect(
      validateBase({
        hello: 'world',
      })
    ).toEqual([missingParameter('base')]);
  });

  it('return error when req.base is invalid', () => {
    expect(
      validateBase({
        base: 123,
      })
    ).toEqual([invalidBaseError]);
  });
});

describe('validateSide', () => {
  it('valid when req.side is a string', () => {
    expect(
      validateSide({
        side: 'BUY',
      })
    ).toEqual([]);

    expect(
      validateSide({
        side: 'SELL',
      })
    ).toEqual([]);
  });

  it('return error when req.side does not exist', () => {
    expect(
      validateSide({
        hello: 'world',
      })
    ).toEqual([missingParameter('side')]);
  });

  it('return error when req.side is invalid', () => {
    expect(
      validateSide({
        side: 'comprar',
      })
    ).toEqual([invalidSideError]);
  });
});

describe('validateLimitPrice', () => {
  it('valid when req.limitPrice is a string', () => {
    expect(
      validateLimitPrice({
        limitPrice: '12000.123',
      })
    ).toEqual([]);

    expect(
      validateLimitPrice({
        limitPrice: '89425894',
      })
    ).toEqual([]);
  });

  it('pass when req.limitPrice does not exist', () => {
    expect(
      validateLimitPrice({
        hello: 'world',
      })
    ).toEqual([]);
  });

  it('return error when req.limitPrice is invalid', () => {
    expect(
      validateLimitPrice({
        limitPrice: 'comprar',
      })
    ).toEqual([invalidLimitPriceError]);
  });
});
