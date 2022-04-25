import { Validator, isFloatString, isFractionString } from './validators';

export const invalidAllowedSlippage: string =
  'allowedSlippage should be a number or a string of a fraction.';

export const missingParameter = (key: string): string => {
  return `The request is missing a key that ends with: ${key}`;
};

// This is a specialized version of mkValidator. Since config parameters are a
// chain of keys, sometimes we want to generalize the validator behavior for
// certain groups of keys (for example: uniswap.versions.v2.allowedSlippage and
// avalanche.allowedSlippage). These keys live in different files but are
// expected to have the same type of permissible values.
export const mkConfigValidator = (
  key: string,
  errorMsg: string,
  condition: (x: any) => boolean,
  optional: boolean = false
): Validator => {
  return (req: any) => {
    let matchingKey: string | null = null;
    for (const reqKey in req) {
      if (reqKey.endsWith(key)) {
        matchingKey = reqKey;
        break;
      }
    }

    const errors: Array<string> = [];
    if (typeof matchingKey === 'string') {
      if (req[matchingKey]) {
        if (!condition(req[matchingKey])) {
          errors.push(errorMsg);
        }
      } else {
        if (!optional) {
          errors.push(missingParameter(key));
        }
      }
    } else {
      if (!optional) {
        errors.push(missingParameter(key));
      }
    }

    return errors;
  };
};

export const validateAllowedSlippage: Validator = mkConfigValidator(
  'allowedSlippage',
  invalidAllowedSlippage,
  (val) =>
    typeof val === 'number' ||
    (typeof val === 'string' && (isFractionString(val) || isFloatString(val)))
);
