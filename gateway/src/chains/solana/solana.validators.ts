import {
  isNaturalNumberString,
  validateTokenSymbols,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
  isBase58,
} from '../../services/validators';
import bs58 from 'bs58';

import {} from '../ethereum/ethereum.validators';

// invalid parameter errors

export const invalidPrivateKeyError: string =
  'The privateKey param is not a valid Solana private key (base58 string worth 32 bytes).';

export const invalidSpenderError: string =
  'The spender param is not a valid Solana public key (base58 string worth 32 bytes).';

export const invalidTokenSymbolsError: string =
  'The tokenSymbols param should be an array of strings.';

export const invalidTokenError: string = 'The token param should be a string.';

export const invalidAmountError: string =
  'If amount is included it must be a string of a non-negative integer.';

export const invalidTxHashError: string = 'The txHash param must be a string.';

// test if a string matches the shape of an Solana public key
export const isPublicKey = (str: string): boolean => {
  return isBase58(str) && bs58.decode(str).length == 32;
};

// test if a string matches the shape of an Solana private key
export const isPrivateKey = (str: string): boolean => {
  return isBase58(str) && bs58.decode(str).length == 32;
};

// given a request, look for a key called privateKey that is an Solana private key
export const validatePrivateKey: Validator = mkValidator(
  'privateKey',
  invalidPrivateKeyError,
  (val) => typeof val === 'string' && isPrivateKey(val)
);

// given a request, look for a key called publicKey that is an Solana public key
export const validatePublicKey: Validator = mkValidator(
  'publicKey',
  invalidSpenderError,
  (val) => typeof val === 'string' && isPublicKey(val)
);

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

// request types and corresponding validators

export const validateSolanaBalanceRequest: RequestValidator =
  mkRequestValidator([validatePrivateKey, validateTokenSymbols]);

export const validateSolanaPollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);

export const validateSolanaGetTokenRequest: RequestValidator =
  mkRequestValidator([validateToken, validatePublicKey]);

export const validateSolanaPostTokenRequest: RequestValidator =
  mkRequestValidator([validateToken, validatePrivateKey]);
