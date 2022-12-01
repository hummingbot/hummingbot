// eslint-disable-next-line
// @ts-ignore
import { HttpException } from '../../../services/error-handler';
import * as cycle from 'cycle';

// eslint-disable-next-line
// @ts-ignore
JSON.originalStringify = JSON.stringify;

// eslint-disable-next-line
// @ts-ignore
JSON.stringify = (
  value: any,
  replacer?: (this: any, key: string, value: any) => any,
  space?: string | number
): string => {
  // eslint-disable-next-line
  // @ts-ignore
  return JSON.originalStringify(cycle.decycle(value), replacer, space);
};

// eslint-disable-next-line
// @ts-ignore
JSON.originalParse = JSON.parse;

JSON.parse = (
  text: string,
  reviver?: (this: any, key: string, value: any) => any
): any => {
  try {
    // eslint-disable-next-line
    // @ts-ignore
    return JSON.originalParse(cycle.retrocycle(text), reviver);
  } catch (exception) {
    // Used to handle internal solana library unhandled exception.
    if (
      text.startsWith('<html>') &&
      text.includes('<head><title>504 Gateway Time-out</title></head>')
    ) {
      throw new HttpException(504, 'Gateway Timeout');
    }

    console.log('text:\n', text, '\nexception:\n', exception);

    throw exception;
  }
};
