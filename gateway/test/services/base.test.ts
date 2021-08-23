import { BigNumber } from 'ethers';
import { bigNumberWithDecimalToStr } from '../../src/services/base';
import 'jest-extended';

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
