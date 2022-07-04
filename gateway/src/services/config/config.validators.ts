import {
  RequestValidator,
  Validator,
  isFloatString,
  isFractionString,
  mkRequestValidator,
} from '../validators';
import { fromFractionString, toFractionString } from '../base';
import { ConfigUpdateRequest } from './config.requests';

export const invalidAllowedSlippage: string =
  'allowedSlippage should be a number between 0.0 and 1.0 or a string of a fraction.';

// only permit percentages 0.0 (inclusive) to less one
export const isAllowedPercentage = (val: string | number): boolean => {
  if (typeof val === 'string') {
    if (isFloatString(val)) {
      const num: number = parseFloat(val);
      return num >= 0.0 && num < 1.0;
    } else {
      const num: number | null = fromFractionString(val); // this checks if it is a fraction string
      if (num !== null) {
        return num >= 0.0 && num < 1.0;
      } else {
        return false;
      }
    }
  } else {
    return val >= 0.0 && val < 1.0;
  }
};

// This is a specialized version of mkValidator for /config/update.
// All requests should be of the form {configPath, configValue}. This allows you
// to create validators that match on configPath, then test the value of configValue.
// (for example: {configPath: 'uniswap.versions.v2.allowedSlippage', configValue: 0.1}.
export const mkConfigValidator = (
  configPathEnding: string,
  errorMsg: string,
  condition: (x: any) => boolean
): Validator => {
  return (req: any) => {
    const errors: Array<string> = [];
    const configPath: string = req.configPath;
    if (configPath.endsWith(configPathEnding)) {
      const configValue = req.configValue;
      if (!condition(configValue)) {
        errors.push(errorMsg);
      }
    }

    return errors;
  };
};

export const validateAllowedSlippage: Validator = mkConfigValidator(
  'allowedSlippage',
  invalidAllowedSlippage,
  (val) =>
    (typeof val === 'number' ||
      (typeof val === 'string' &&
        (isFractionString(val) || isFloatString(val)))) &&
    isAllowedPercentage(val)
);

export const validateConfigUpdateRequest: RequestValidator = mkRequestValidator(
  [validateAllowedSlippage]
);

// this mutates the input value in place
export const updateAllowedSlippageToFraction = (
  body: ConfigUpdateRequest
): void => {
  if (body.configPath.endsWith('allowedSlippage')) {
    if (
      typeof body.configValue === 'number' ||
      (typeof body.configValue == 'string' &&
        !isFractionString(body.configValue))
    ) {
      body.configValue = toFractionString(body.configValue);
    }
  }
};
