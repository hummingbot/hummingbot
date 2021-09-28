import {
  isNaturalNumberString,
  isFloatString,
  missingParameter,
  throwErrorsIfExist,
} from '../../../services/validators';

import { validateNonce, validatePrivateKey } from '../ethereum.validators';

import { UniswapPriceRequest, UniswapTradeRequest } from './uniswap.requests';

export const invalidQuoteError: string = 'The quote param is not a string.';

export const invalidBaseError: string = 'The base param is not a string.';

export const invalidAmountError: string =
  'The amount param must be a string of a non-negative integer.';

export const invalidSideError: string =
  'The side param must be a string of "buy" or "sell".';

export const invalidLimitPriceError: string =
  'The limitPrice param may be null or a string of a float or integer number.';

export const validateQuote = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.quote) {
    if (typeof req.quote === 'string') {
    } else {
      errors.push(invalidQuoteError);
    }
  } else {
    errors.push(missingParameter('quote'));
  }
  return errors;
};

export const validateBase = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.base) {
    if (typeof req.base === 'string') {
    } else {
      errors.push(invalidBaseError);
    }
  } else {
    errors.push(missingParameter('base'));
  }
  return errors;
};

export const validateAmount = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.amount) {
    if (typeof req.amount === 'string' && isNaturalNumberString(req.amount)) {
    } else {
      errors.push(invalidAmountError);
    }
  } else {
    errors.push(missingParameter('amount'));
  }
  return errors;
};

export const validateSide = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.side) {
    if (
      typeof req.side === 'string' &&
      (req.side === 'BUY' || req.side === 'SELL')
    ) {
    } else {
      errors.push(invalidSideError);
    }
  } else {
    errors.push(missingParameter('side'));
  }
  return errors;
};

export const validateLimitPrice = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.limitPrice) {
    if (typeof req.limitPrice === 'string' && isFloatString(req.limitPrice)) {
    } else {
      errors.push(invalidLimitPriceError);
    }
  }
  return errors;
};

export const validateUniswapPriceRequest = (req: UniswapPriceRequest): void => {
  const errors = validateQuote(req).concat(
    validateBase(req),
    validateAmount(req),
    validateSide(req)
  );
  throwErrorsIfExist(errors);
};

export const validateUniswapTradeRequest = (req: UniswapTradeRequest): void => {
  const errors = validateQuote(req).concat(
    validateBase(req),
    validateAmount(req),
    validatePrivateKey(req),
    validateSide(req),
    validateLimitPrice(req),
    validateNonce(req)
  );
  throwErrorsIfExist(errors);
};
