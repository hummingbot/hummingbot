import {
  invalidMarkerError,
  validateMarket,
  invalidPriceError,
  validatePrice,
  invalidWalletError,
  validateWallet,
  invalidOrderIdError,
  validateOrderId,
} from '../../src/clob/clob.validators';

import { missingParameter } from '../../src/services/validators';

import 'jest-extended';

describe('validateMarket', () => {
  it('valid when req.market is a ', () => {
    expect(
      validateMarket({
        market: 'DAI-USDT',
      })
    ).toEqual([]);

    expect(
      validateMarket({
        market: 'WBTC-DAI',
      })
    ).toEqual([]);
  });

  it('return error when req.market does not exist', () => {
    expect(
      validateMarket({
        hello: 'world',
      })
    ).toEqual([missingParameter('market')]);
  });

  it('return error when req.market is invalid', () => {
    expect(
      validateMarket({
        market: 'BTC',
      })
    ).toEqual([invalidMarkerError]);
  });
});

describe('validatePrice', () => {
  it('valid when req.price is a string', () => {
    expect(
      validatePrice({
        price: '10.5',
      })
    ).toEqual([]);

    expect(
      validatePrice({
        price: '0.31',
      })
    ).toEqual([]);
  });

  it('return error when req.price is invalid', () => {
    expect(
      validatePrice({
        price: 123,
      })
    ).toEqual([invalidPriceError]);
  });
});

describe('validateWallet', () => {
  it('valid when req.address is a string', () => {
    expect(
      validateWallet({
        address:
          '0x261362dbc1d83705ab03e99792355689a4589b8e000000000000000000000000', // noqa: mock
      })
    ).toEqual([]);

    expect(
      validateWallet({
        address:
          '0xdefe33795803f2353c69fd8cdb432f9d5cee6762000000000000000000000000', // noqa: mock
      })
    ).toEqual([]);
  });

  it('return error when req.address does not exist', () => {
    expect(
      validateWallet({
        hello: 'world',
      })
    ).toEqual([missingParameter('address')]);
  });

  it('return error when req.address is invalid', () => {
    expect(
      validateWallet({
        address: 123,
      })
    ).toEqual([invalidWalletError]);
  });
});

describe('validateOrderId', () => {
  it('valid when req.orderId is a string', () => {
    expect(
      validateOrderId({
        orderId:
          '0x36dfcb66f2aa865df5c30ecafc210786d232089009df804381e5ad54fb6ae9bd', // noqa: mock
      })
    ).toEqual([]);

    expect(
      validateOrderId({
        orderId:
          '0x916e7a23539495ba0bf2a41ae096f894a2588cf0f004467f1c1e609dcf16f05f', // noqa: mock
      })
    ).toEqual([]);
  });

  it('pass when req.orderId does not exist', () => {
    expect(
      validateOrderId({
        hello: 'world',
      })
    ).toEqual([missingParameter('orderId')]);
  });

  it('return error when req.orderId is invalid', () => {
    expect(
      validateOrderId({
        orderId: 123,
      })
    ).toEqual([invalidOrderIdError]);
  });
});
