import {
  isNaturalNumberString,
  missingParameter,
  throwErrorsIfExist,
} from '../../services/validators';

import {
  EthereumNonceRequest,
  EthereumAllowancesRequest,
  EthereumBalanceRequest,
  EthereumApproveRequest,
} from './ethereum.requests';

// validate request parameters

// test if a string matches the shape of an Ethereum public key
export const isPublicKey = (str: string): boolean => {
  return /^0x[a-fA-F0-9]{40}$/.test(str);
};

// test if a string matches the shape of an Ethereum private key
export const isPrivateKey = (str: string): boolean => {
  return /^[a-fA-F0-9]{64}$/.test(str);
};

// invalid parameter errors

export const invalidPrivateKeyError: string =
  'The privateKey param is not a valid Ethereum private key (64 hexidecimal characters).';

export const invalidSpenderError: string =
  'The spender param is not a valid Ethereum public key (0x followed by 40 hexidecimal characters).';

export const invalidTokenSymbolsError: string =
  'The tokenSymbols param should be an array of strings.';

export const invalidAmountError: string =
  'If amount is included it must be a string of a non-negative integer.';

export const invalidNonceError: string =
  'If nonce is included it must be a non-negative integer.';

// given a request, look for a key called privateKey that is an Ethereum private key
export const validatePrivateKey = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.privateKey) {
    if (typeof req.privateKey === 'string' && isPrivateKey(req.privateKey)) {
    } else {
      errors.push(invalidPrivateKeyError);
    }
  } else {
    errors.push(missingParameter('privateKey'));
  }
  return errors;
};

// given a request, look for a key called spender that is 'uniswap' or an Ethereum public key
export const validateSpender = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.spender) {
    if (
      typeof req.spender === 'string' &&
      (req.spender === 'uniswap' || isPublicKey(req.spender))
    ) {
    } else {
      errors.push(invalidSpenderError);
    }
  } else {
    errors.push(missingParameter('spender'));
  }
  return errors;
};

// confirm that tokenSymbols is an array of strings
export const validateTokenSymbols = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.tokenSymbols) {
    if (Array.isArray(req.tokenSymbols)) {
      req.tokenSymbols.forEach((symbol: any) => {
        if (typeof symbol === 'string') {
        } else {
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

// if amount exists, confirm that it is a string of a natural number
export const validateAmount = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.amount) {
    if (typeof req.amount === 'string' && isNaturalNumberString(req.amount)) {
    } else {
      errors.push(invalidAmountError);
    }
  }
  return errors;
};

export const validateNonce = (req: any): Array<string> => {
  let errors: Array<string> = [];
  if (req.nonce) {
    if (typeof req.nonce === 'number' && req.nonce > -1) {
    } else {
      errors.push(invalidNonceError);
    }
  }
  return errors;
};

// request types and corresponding validators

export const validateEthereumNonceRequest = (
  req: EthereumNonceRequest
): void => {
  throwErrorsIfExist(validatePrivateKey(req));
};

export const validateEthereumAllowancesRequest = (
  req: EthereumAllowancesRequest
): void => {
  const errors = validatePrivateKey(req)
    .concat(validateSpender(req))
    .concat(validateTokenSymbols(req));
  throwErrorsIfExist(errors);
};

export const validateEthereumBalanceRequest = (
  req: EthereumBalanceRequest
): void => {
  const errors = validatePrivateKey(req).concat(validateTokenSymbols(req));
  throwErrorsIfExist(errors);
};

export const validateEthereumApproveRequest = (
  req: EthereumApproveRequest
): void => {
  const errors = validatePrivateKey(req).concat(
    validateSpender(req),
    validateTokenSymbols(req),
    validateAmount(req),
    validateNonce(req)
  );
  throwErrorsIfExist(errors);
};
