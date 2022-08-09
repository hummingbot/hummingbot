import {
  validateTokenSymbols,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
  // isBase58,
  validateTxHash,
} from '../../services/validators';
// import bs58 from 'bs58';

// invalid parameter errors
export const invalidPrivateKeyError: string =
  'The privateKey param is not a valid Cosmos private key (base58 string worth 64 bytes).';

export const invalidCosmosAddressError: string =
  'The spender param is not a valid Cosmos address.';

// TODO: Update to match the cosmos address format
export const isValidCosmosAddress = (str: string): boolean => {
  console.log(str);
  return true;
  // return isBase58(str) && bs58.decode(str).length == 32;
};

// given a request, look for a key called address that is a Cosmos address
export const validatePublicKey: Validator = mkValidator(
  'address',
  invalidCosmosAddressError,
  (val) => typeof val === 'string' && isValidCosmosAddress(val)
);

// request types and corresponding validators

export const validateCosmosBalanceRequest: RequestValidator =
  mkRequestValidator([validatePublicKey, validateTokenSymbols]);

export const validateCosmosPollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);
