import { HttpException } from './error-handler';

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
