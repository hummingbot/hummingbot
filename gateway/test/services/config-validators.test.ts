import {
  invalidAllowedSlippage,
  validateAllowedSlippage,
  updateAllowedSlippageToFraction,
} from '../../src/services/config/config.validators';
import 'jest-extended';

describe('validateAllowedSlippage', () => {
  it('valid when req.uniswap.versions.v2.allowedSlippage is a fraction string', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'req.uniswap.versions.v2.allowedSlippage',
        configValue: '1/100',
      })
    ).toEqual([]);
  });

  it('valid when req.uniswap.versions.v2.allowedSlippage is a number', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'avalanche.allowedSlippage',
        configValue: 0.1,
      })
    ).toEqual([]);
  });

  it('valid when req.avalanche.allowedSlippage is a fraction string', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'req.avalanche.allowedSlippage',
        configValue: '3/10',
      })
    ).toEqual([]);
  });

  it('valid when req.avalanche.allowedSlippage is a float string', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'req.avalanche.allowedSlippage',
        configValue: '0.005',
      })
    ).toEqual([]);
  });

  it('valid when req.avalanche.allowedSlippage is a float string', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'req.avalanche.allowedSlippage',
        configValue: '0.005',
      })
    ).toEqual([]);
  });

  it('valid when req.avalanche.allowedSlippage is a number', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'avalanche.allowedSlippage',
        configValue: 0.005,
      })
    ).toEqual([]);
  });

  it('invalid when req.avalanche.allowedSlippage is too large (number)', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'avalanche.allowedSlippage',
        configValue: 1.005,
      })
    ).toEqual([invalidAllowedSlippage]);
  });

  it('invalid when req.avalanche.allowedSlippage is too large (fraction)', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'avalanche.allowedSlippage',
        configValue: '3/2',
      })
    ).toEqual([invalidAllowedSlippage]);
  });

  it('invalid when req.avalanche.allowedSlippage is too small (number)', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'avalanche.allowedSlippage',
        configValue: -1.005,
      })
    ).toEqual([invalidAllowedSlippage]);
  });

  it('invalid when req.avalanche.allowedSlippage is too small (fraction)', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'avalanche.allowedSlippage',
        configValue: '-1/5',
      })
    ).toEqual([invalidAllowedSlippage]);
  });

  it('valid when configPath is not allowedSlippage does not exist', () => {
    expect(
      validateAllowedSlippage({ configPath: 'hello', configValue: 'world' })
    ).toEqual([]);
  });

  it('invalid when req.avalanche.allowedSlippage is a non-numerical string', () => {
    expect(
      validateAllowedSlippage({
        configPath: 'avalanche.allowedSlippage',
        configValue: 'hello',
      })
    ).toEqual([invalidAllowedSlippage]);
  });
});

describe('updateAllowedSlippageToFraction', () => {
  it('update when req.uniswap.versions.v2.allowedSlippage is a number', () => {
    const body = { configPath: 'avalanche.allowedSlippage', configValue: 0.1 };
    updateAllowedSlippageToFraction(body);
    expect(body.configValue).toEqual('1/10');
  });

  it('update when req.uniswap.versions.v2.allowedSlippage is a number string', () => {
    const body = { configPath: 'avalanche.allowedSlippage', configValue: 0.25 };
    updateAllowedSlippageToFraction(body);
    expect(body.configValue).toEqual('1/4');
  });

  it('do nothing when req.uniswap.versions.v2.allowedSlippage is a fraction', () => {
    const body = {
      configPath: 'avalanche.allowedSlippage',
      configValue: '1/5',
    };
    updateAllowedSlippageToFraction(body);
    expect(body.configValue).toEqual('1/5');
  });

  it('do nothing when the configPath is not allowedSlippage', () => {
    const body = { configPath: 'hellow', configValue: 'goodbye' };
    updateAllowedSlippageToFraction(body);
    expect(body.configValue).toEqual('goodbye');
  });
});
