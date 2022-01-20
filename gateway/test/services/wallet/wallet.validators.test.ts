import {
  invalidPrivateKeyError,
  isPrivateKey,
  validatePrivateKey,
  invalidChainNameError,
  invalidAddressError,
  validateChainName,
  validateAddress,
} from '../../../src/services/wallet/wallet.validators';

import { missingParameter } from '../../../src/services/validators';

import 'jest-extended';

describe('isPrivateKey', () => {
  it('pass against a well formed public key', () => {
    expect(
      isPrivateKey(
        'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4' // noqa: mock
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
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4', // noqa: mock
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

describe('validateChainName', () => {
  it('valid when chainName is ethereum', () => {
    expect(
      validateChainName({
        chainName: 'ethereum',
      })
    ).toEqual([]);
  });

  it('valid when chainName is avalanche', () => {
    expect(
      validateChainName({
        chainName: 'avalanche',
      })
    ).toEqual([]);
  });

  it('return error when req.chainName does not exist', () => {
    expect(
      validateChainName({
        hello: 'world',
      })
    ).toEqual([missingParameter('chainName')]);
  });

  it('return error when req.chainName is invalid', () => {
    expect(
      validateChainName({
        chainName: 'shibainu',
      })
    ).toEqual([invalidChainNameError]);
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
