import {
  invalidEthPrivateKeyError,
  isEthPrivateKey,
  validatePrivateKey,
  invalidChainError,
  invalidAddressError,
  validateChain,
  validateAddress,
  isSolPrivateKey,
  invalidSolPrivateKeyError,
  isNearPrivateKey,
} from '../../../src/services/wallet/wallet.validators';

import { missingParameter } from '../../../src/services/validators';

import 'jest-extended';

describe('isEthPrivateKey', () => {
  it('pass against a well formed private key', () => {
    expect(
      isEthPrivateKey(
        'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4' // noqa: mock
      )
    ).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(isEthPrivateKey('da857cbda0ba96757fed842617a40693d0')).toEqual(
      false
    );
  });

  it('fail against a string that has non-hexadecimal characters', () => {
    expect(
      isEthPrivateKey(
        'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747qwer'
      )
    ).toEqual(false);
  });
});

describe('isSolPrivateKey', () => {
  it('pass against a well formed base58 private key', () => {
    expect(
      isSolPrivateKey(
        '5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHJefiTt'
      )
    ).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(
      isSolPrivateKey('5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4')
    ).toEqual(false);
  });

  it('fail against a string that has non-base58 characters', () => {
    expect(
      isSolPrivateKey(
        '5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHO0O0O0'
      )
    ).toEqual(false);
  });
});

describe('isNearPrivateKey', () => {
  it('pass against a well formed private key', () => {
    expect(
      isNearPrivateKey(
        'ed25519:5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHJefiTt'
      )
    ).toEqual(true);
  });

  it('fail against a string that is invalid', () => {
    expect(isSolPrivateKey('ed25519')).toEqual(false);
  });
});

describe('validatePrivateKey', () => {
  it('valid when req.privateKey is an ethereum key', () => {
    expect(
      validatePrivateKey({
        chain: 'ethereum',
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4', // noqa: mock
      })
    ).toEqual([]);
  });

  it('valid when req.privateKey is a near key', () => {
    expect(
      validatePrivateKey({
        chain: 'near',
        privateKey:
          'ed25519:5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHJefiTt',
      })
    ).toEqual([]);
  });

  it('valid when req.privateKey is a harmony key', () => {
    expect(
      validatePrivateKey({
        chain: 'harmony',
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4', // noqa: mock
      })
    ).toEqual([]);
  });

  it('valid when req.privateKey is a cronos key', () => {
    expect(
      validatePrivateKey({
        chain: 'cronos',
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4', // noqa: mock
      })
    ).toEqual([]);
  });

  it('valid when req.privateKey is a polygon key', () => {
    expect(
      validatePrivateKey({
        chain: 'polygon',
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4', // noqa: mock
      })
    ).toEqual([]);
  });

  it('valid when req.privateKey is a avalanche key', () => {
    expect(
      validatePrivateKey({
        chain: 'avalanche',
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4', // noqa: mock
      })
    ).toEqual([]);
  });

  it('valid when req.privateKey is a solana key', () => {
    expect(
      validatePrivateKey({
        chain: 'solana',
        privateKey:
          '5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHJefiTt',
      })
    ).toEqual([]);
  });

  it('valid when req.privateKey is an binance-smart-chain key', () => {
    expect(
      validatePrivateKey({
        chain: 'binance-smart-chain',
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4', // noqa: mock
      })
    ).toEqual([]);
  });

  it('return error when req.privateKey does not exist', () => {
    expect(
      validatePrivateKey({
        chain: 'ethereum',
        hello: 'world',
      })
    ).toEqual([missingParameter('privateKey')]);
  });

  it('return error when req.chain does not exist', () => {
    expect(
      validatePrivateKey({
        privateKey:
          '5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHJefiTt',
      })
    ).toEqual([missingParameter('chain')]);
  });

  it('return error when req.privateKey is invalid ethereum key', () => {
    expect(
      validatePrivateKey({
        chain: 'ethereum',
        privateKey: 'world',
      })
    ).toEqual([invalidEthPrivateKeyError]);
  });

  it('return error when req.privateKey is invalid solana key', () => {
    expect(
      validatePrivateKey({
        chain: 'solana',
        privateKey: 'world',
      })
    ).toEqual([invalidSolPrivateKeyError]);
  });

  it('return error when req.privateKey is invalid binance-smart-chain key', () => {
    expect(
      validatePrivateKey({
        chain: 'binance-smart-chain',
        privateKey: 'someErroneousPrivateKey',
      })
    ).toEqual([invalidEthPrivateKeyError]);
  });
});

describe('validateChain', () => {
  it('valid when chain is ethereum', () => {
    expect(
      validateChain({
        chain: 'ethereum',
      })
    ).toEqual([]);
  });

  it('valid when chain is avalanche', () => {
    expect(
      validateChain({
        chain: 'avalanche',
      })
    ).toEqual([]);
  });

  it('valid when chain is solana', () => {
    expect(
      validateChain({
        chain: 'solana',
      })
    ).toEqual([]);
  });

  it('valid when chain is harmony', () => {
    expect(
      validateChain({
        chain: 'harmony',
      })
    ).toEqual([]);
  });

  it('valid when chain is binance-smart-chain', () => {
    expect(
      validateChain({
        chain: 'binance-smart-chain',
      })
    ).toEqual([]);
  });

  it('valid when chain is cronos', () => {
    expect(
      validateChain({
        chain: 'cronos',
      })
    ).toEqual([]);
  });

  it('valid when chain is binance-smart-chain', () => {
    expect(
      validateChain({
        chain: 'binance-smart-chain',
      })
    ).toEqual([]);
  });

  it('return error when req.chain does not exist', () => {
    expect(
      validateChain({
        hello: 'world',
      })
    ).toEqual([missingParameter('chain')]);
  });

  it('return error when req.chain is invalid', () => {
    expect(
      validateChain({
        chain: 'shibainu',
      })
    ).toEqual([invalidChainError]);
  });
});

describe('validateAddress', () => {
  it('valid when address is a string', () => {
    expect(
      validateAddress({
        address: '0x000000000000000000000000000000000000000',
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

  it('return error when req.address is not a string', () => {
    expect(
      validateAddress({
        address: 1,
      })
    ).toEqual([invalidAddressError]);
  });
});
