import { BigNumber } from 'ethers';
import {
  bigNumberWithDecimalToStr,
  gasCostInEthString,
  countDecimals,
} from '../../src/services/base';
import 'jest-extended';

test('countDecimals', () => {
  const rangeError = 'countDecimals() is only valid for values between (0, 1).';
  expect(() => countDecimals(0)).toThrow(rangeError);
  expect(() => countDecimals(1)).toThrow(rangeError);
  expect(() => countDecimals(-1)).toThrow(rangeError);
  expect(() => countDecimals(100)).toThrow(rangeError);
  expect(() => countDecimals(1.0000123)).toThrow(rangeError);
  expect(() => countDecimals(100.0000123)).toThrow(rangeError);
  expect(() => countDecimals(1e9)).toThrow(rangeError);
  expect(countDecimals(0.0000123)).toEqual(5);
  expect(countDecimals(1e-9)).toEqual(9);
});

test('bigNumberWithDecimalToStr', () => {
  expect(bigNumberWithDecimalToStr(BigNumber.from(10), 1)).toEqual('1.0');

  expect(bigNumberWithDecimalToStr(BigNumber.from(1), 1)).toEqual('0.1');

  expect(bigNumberWithDecimalToStr(BigNumber.from(12345), 8)).toEqual(
    '0.00012345'
  );

  expect(
    bigNumberWithDecimalToStr(BigNumber.from('8447700000000000000'), 18)
  ).toEqual('8.447700000000000000');

  expect(
    bigNumberWithDecimalToStr(BigNumber.from('1200304050607080001'), 18)
  ).toEqual('1.200304050607080001');

  expect(
    bigNumberWithDecimalToStr(BigNumber.from('1345000000000000000000'), 18)
  ).toEqual('1345.000000000000000000');
});

test('gasCostInEthString', () => {
  expect(gasCostInEthString(200, 21000)).toEqual('0.004200000000000000');
});
