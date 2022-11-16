import { HttpException } from './error-handler';

export const invalidAmountError: string =
  'If amount is included it must be a string of a non-negative integer.';

export const invalidTokenError: string = 'The token param should be a string.';

export const invalidTxHashError: string = 'The txHash param must be a string.';

export const invalidTokenSymbolsError: string =
  'The tokenSymbols param should be an array of strings.';

export const isNaturalNumberString = (str: string): boolean => {
  return /^[0-9]+$/.test(str);
};

export const isIntegerString = (str: string): boolean => {
  return /^[+-]?[0-9]+$/.test(str);
};

export const isFloatString = (str: string): boolean => {
  if (isIntegerString(str)) {
    return true;
  }
  const decimalSplit = str.split('.');
  if (decimalSplit.length === 2) {
    return (
      isIntegerString(decimalSplit[0]) && isNaturalNumberString(decimalSplit[1])
    );
  }
  return false;
};

export const isFractionString = (str: string): boolean => {
  const fractionSplit = str.split('/');
  if (fractionSplit.length == 2) {
    return (
      isIntegerString(fractionSplit[0]) && isIntegerString(fractionSplit[1])
    );
  }
  return false;
};

// throw an error because the request parameter is malformed, collect all the
// errors related to the request to give the most information possible
export const throwIfErrorsExist = (errors: Array<string>): void => {
  if (errors.length > 0) {
    throw new HttpException(404, errors.join(', '));
  }
};

export const missingParameter = (key: string): string => {
  return `The request is missing the key: ${key}`;
};

export type Validator = (req: any) => Array<string>;

export type RequestValidator = (req: any) => void;

export const mkBranchingValidator = (
  branchingKey: string,
  branchingCondition: (req: any, key: string) => boolean,
  validator1: Validator,
  validator2: Validator
): Validator => {
  return (req: any) => {
    let errors: Array<string> = [];
    if (req[branchingKey]) {
      if (branchingCondition(req, branchingKey)) {
        errors = errors.concat(validator1(req));
      } else {
        errors = errors.concat(validator2(req));
      }
    } else {
      errors.push(missingParameter(branchingKey));
    }
    return errors;
  };
};

export const mkSelectingValidator = (
  branchingKey: string,
  branchingCondition: (req: any, key: string) => string,
  validators: { [id: string]: Validator }
): Validator => {
  return (req: any) => {
    let errors: Array<string> = [];
    if (req[branchingKey]) {
      if (
        Object.keys(validators).includes(branchingCondition(req, branchingKey))
      ) {
        errors = errors.concat(
          validators[branchingCondition(req, branchingKey)](req)
        );
      } else {
        errors.push(
          `No validator exists for ${branchingCondition(req, branchingKey)}.`
        );
      }
    } else {
      errors.push(missingParameter(branchingKey));
    }
    return errors;
  };
};

export const mkValidator = (
  key: string,
  errorMsg: string,
  condition: (x: any) => boolean,
  optional: boolean = false
): Validator => {
  return (req: any) => {
    const errors: Array<string> = [];
    if (req[key]) {
      if (!condition(req[key])) {
        errors.push(errorMsg);
      }
    } else {
      if (!optional) {
        errors.push(missingParameter(key));
      }
    }

    return errors;
  };
};

export const mkRequestValidator = (
  validators: Array<Validator>
): RequestValidator => {
  return (req: any) => {
    let errors: Array<string> = [];
    validators.forEach(
      (validator: Validator) => (errors = errors.concat(validator(req)))
    );
    throwIfErrorsExist(errors);
  };
};

// confirm that tokenSymbols is an array of strings
export const validateTokenSymbols: Validator = (req: any) => {
  const errors: Array<string> = [];
  if (req.tokenSymbols) {
    if (Array.isArray(req.tokenSymbols)) {
      req.tokenSymbols.forEach((symbol: any) => {
        if (typeof symbol !== 'string') {
          errors.push(invalidTokenSymbolsError);
        }
      });
    } else {
      errors.push(invalidTokenSymbolsError);
    }
  } else {
    errors.push(missingParameter('tokenSymbols'));
  }
  return errors;
};

export const isBase58 = (value: string): boolean =>
  /^[A-HJ-NP-Za-km-z1-9]*$/.test(value);

// confirm that token is a string
export const validateToken: Validator = mkValidator(
  'token',
  invalidTokenError,
  (val) => typeof val === 'string'
);

// if amount exists, confirm that it is a string of a natural number
export const validateAmount: Validator = mkValidator(
  'amount',
  invalidAmountError,
  (val) => typeof val === 'string' && isNaturalNumberString(val),
  true
);

export const validateTxHash: Validator = mkValidator(
  'txHash',
  invalidTxHashError,
  (val) => typeof val === 'string'
);
