import { BigNumber } from 'ethers';

// the type of information source for tokens
export type TokenListType = 'FILE' | 'URL';

// insert a string into another string at an index
const stringInsert = (str: string, val: string, index: number) => {
  if (index > 0) {
    return str.substring(0, index) + val + str.substr(index);
  }

  return val + str;
};

// convert a BigNumber and the number of decimals into a numeric string.
// this makes it JavaScript compatible while preserving all the data.
export const bigNumberWithDecimalToStr = (n: BigNumber, d: number): string => {
  const n_ = n.toString();

  let zeros = '';

  if (n_.length <= d) {
    zeros = '0'.repeat(d - n_.length + 1);
  }

  return stringInsert(n_.split('').reverse().join('') + zeros, '.', d)
    .split('')
    .reverse()
    .join('');
};

// a nice way to represent the token value without carrying around as a string
export interface TokenValue {
  value: BigNumber;
  decimals: number;
}

// we should turn Token into a string when we return as a value in an API call
export const tokenValueToString = (t: TokenValue): string => {
  return bigNumberWithDecimalToStr(t.value, t.decimals);
};

// safely parse a JSON from a string to a type.
export const safeJsonParse =
  <T>(guard: (o: any) => o is T) =>
  (text: string): ParseResult<T> => {
    const parsed = JSON.parse(text);
    return guard(parsed) ? { parsed, hasError: false } : { hasError: true };
  };

// If the JSON was parsed successfully, return the result, otherwises return the error
export type ParseResult<T> =
  | { parsed: T; hasError: false; error?: undefined }
  | { parsed?: undefined; hasError: true; error?: unknown };

export const latency = (startTime: number, endTime: number): number => {
  return (endTime - startTime) / 1000;
};
