import {
  invalidPrivateKeyError,
  isPrivateKey,
  validatePrivateKey,
  invalidChainError,
  invalidAddressError,
  validateChain,
  validateAddress,
} from '../../../src/services/wallet/wallet.validators';

import { missingParameter } from '../../../src/services/validators';

import 'jest-extended';

describe('isPrivateKey', () => {
  it('pass against a well formed public key', () => {
    expect(
      isPrivateKey(
        'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4'
      )
    ).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(isPrivateKey('da857cbda0ba96757fed842617a40693d0')).toEqual(false);
  });

  it('fail against a string that has non-hexadecimal characters', () => {
    expect(
      isPrivateKey(
        'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747qwer'
      )
    ).toEqual(false);
  });
});

describe('validatePrivateKey', () => {
  it('valid when req.privateKey is a privateKey', () => {
    expect(
      validatePrivateKey({
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4',
      })
    ).toEqual([]);
  });

  it('return error when req.privateKey does not exist', () => {
    expect(
      validatePrivateKey({
        hello: 'world',
      })
    ).toEqual([missingParameter('privateKey')]);
  });

  it('return error when req.privateKey is invalid', () => {
    expect(
      validatePrivateKey({
        privateKey: 'world',
      })
    ).toEqual([invalidPrivateKeyError]);
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
