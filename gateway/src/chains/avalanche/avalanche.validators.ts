import {
  mkRequestValidator,
  mkValidator,
  RequestValidator,
  Validator,
} from '../../services/validators';
import {
  isPublicKey,
  validateAmount,
  validateNonce,
  validatePrivateKey,
  validateToken,
  validateTokenSymbols,
} from '../ethereum/ethereum.validators';

export const invalidSpenderError: string =
  'The spender param is not a valid Avalanche public key (0x followed by 40 hexidecimal characters).';

// given a request, look for a key called spender that is 'uniswap' or an Ethereum public key
export const validateSpender: Validator = mkValidator(
  'spender',
  invalidSpenderError,
  (val) => typeof val === 'string' && (val === 'pangolin' || isPublicKey(val))
);

export const validateAvalancheApproveRequest: RequestValidator =
  mkRequestValidator([
    validatePrivateKey,
    validateSpender,
    validateToken,
    validateAmount,
    validateNonce,
  ]);

export const validateAvalancheAllowancesRequest: RequestValidator =
  mkRequestValidator([
    validatePrivateKey,
    validateSpender,
    validateTokenSymbols,
  ]);
