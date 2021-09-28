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
export const throwErrorsIfExist = (errors: Array<string>): void => {
  if (errors.length > 0) {
    throw new HttpException(404, errors.join(', '));
  }
};

export const missingParameter = (key: string): string => {
  return `The request is missing the private key: ${key}`;
};

export const validate = (
  key: string,
  errorMsg: string,
  condition: (x: any) => boolean,
  optional: boolean = false
): ((req: any) => Array<string>) => {
  return (req: any) => {
    let errors: Array<string> = [];
    if (req[key]) {
      if (condition(req[key])) {
      } else {
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
