import {
  invalidChainNameError,
  invalidAddressError,
  validateChainName,
  validateAddress,
  // validateAddWalletRequest,
  // validateRemoveWalletRequest
} from '../../../src/services/wallet/wallet.validators';

import { missingParameter } from '../../../src/services/validators';

import 'jest-extended';

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
