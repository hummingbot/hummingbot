import {
  invalidAllowedSlippage,
  validateAllowedSlippage,
  missingParameter,
} from '../../src/services/config-validators';
import 'jest-extended';

describe('validateAllowedSlippage', () => {
  it('valid when req.uniswap.versions.v2.allowedSlippage is a fraction string', () => {
    expect(
      validateAllowedSlippage({
        'req.uniswap.versions.v2.allowedSlippage': '1/100',
      })
    ).toEqual([]);
  });

  it('valid when req.uniswap.versions.v2.allowedSlippage is a number', () => {
    expect(
      validateAllowedSlippage({ 'avalanche.allowedSlippage': 0.1 })
    ).toEqual([]);
  });

  it('valid when req.avalanche.allowedSlippage is a fraction string', () => {
    expect(
      validateAllowedSlippage({ 'req.avalanche.allowedSlippage': '3/10' })
    ).toEqual([]);
  });

  it('valid when req.avalanche.allowedSlippage is a float string', () => {
    expect(
      validateAllowedSlippage({ 'req.avalanche.allowedSlippage': '0.005' })
    ).toEqual([]);
  });

  it('valid when req.avalanche.allowedSlippage is a float string', () => {
    expect(
      validateAllowedSlippage({ 'req.avalanche.allowedSlippage': '0.005' })
    ).toEqual([]);
  });

  it('valid when req.avalanche.allowedSlippage is a number', () => {
    expect(
      validateAllowedSlippage({ 'avalanche.allowedSlippage': 0.005 })
    ).toEqual([]);
  });

  it('invalid when req.avalanche.allowedSlippage is too large (number)', () => {
    expect(
      validateAllowedSlippage({ 'avalanche.allowedSlippage': 1.005 })
    ).toEqual([invalidAllowedSlippage]);
  });

  it('invalid when req.avalanche.allowedSlippage is too large (fraction)', () => {
    expect(
      validateAllowedSlippage({ 'avalanche.allowedSlippage': '3/2' })
    ).toEqual([invalidAllowedSlippage]);
  });

  it('invalid when req.avalanche.allowedSlippage is too small (number)', () => {
    expect(
      validateAllowedSlippage({ 'avalanche.allowedSlippage': -1.005 })
    ).toEqual([invalidAllowedSlippage]);
  });

  it('invalid when req.avalanche.allowedSlippage is too small (fraction)', () => {
    expect(
      validateAllowedSlippage({ 'avalanche.allowedSlippage': '-1/5' })
    ).toEqual([invalidAllowedSlippage]);
  });

  it('invalid when req.allowedSlippage does not exist', () => {
    expect(validateAllowedSlippage({ hello: 'world' })).toEqual([
      missingParameter('allowedSlippage'),
    ]);
  });

  it('invalid when req.avalanche.allowedSlippage is a non-numerical string', () => {
    expect(
      validateAllowedSlippage({ 'avalanche.allowedSlippage': 'hello' })
    ).toEqual([invalidAllowedSlippage]);
  });
});
