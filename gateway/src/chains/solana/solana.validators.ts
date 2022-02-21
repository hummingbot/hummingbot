import {
  validateTokenSymbols,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
  isBase58,
  validateTxHash,
  validateToken,
} from '../../services/validators';
import bs58 from 'bs58';

// invalid parameter errors

export const invalidPrivateKeyError: string =
  'The privateKey param is not a valid Solana private key (base58 string worth 64 bytes).';

export const invalidPublicKeyError: string =
  'The spender param is not a valid Solana address (base58 string worth 32 bytes).';

// test if a string matches the shape of an Solana address
export const isPublicKey = (str: string): boolean => {
  return isBase58(str) && bs58.decode(str).length == 32;
};

// given a request, look for a key called address that is an Solana address
export const validatePublicKey: Validator = mkValidator(
  'address',
  invalidPublicKeyError,
  (val) => typeof val === 'string' && isPublicKey(val)
);

// request types and corresponding validators

export const validateSolanaBalanceRequest: RequestValidator =
  mkRequestValidator([validatePublicKey, validateTokenSymbols]);

export const validateSolanaPollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);

export const validateSolanaGetTokenRequest: RequestValidator =
  mkRequestValidator([validateToken, validatePublicKey]);

export const validateSolanaPostTokenRequest: RequestValidator =
  mkRequestValidator([validateToken, validatePublicKey]);
