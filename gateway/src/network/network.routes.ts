/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Request, Response, Router } from 'express';
import * as ethereumControllers from '../chains/ethereum/ethereum.controllers';
import { Solanaish } from '../chains/solana/solana';
import * as solanaControllers from '../chains/solana/solana.controllers';
import * as rippleControllers from '../chains/ripple/ripple.controllers';
import { Ethereumish } from '../services/common-interfaces';
import { ConfigManagerV2 } from '../services/config-manager-v2';
import { getChain } from '../services/connection-manager';
import { asyncHandler } from '../services/error-handler';
import {
  mkRequestValidator,
  RequestValidator,
  validateTxHash,
} from '../services/validators';
import { getStatus, getTokens } from './network.controllers';
import {
  BalanceRequest,
  BalanceResponse,
  PollRequest,
  PollResponse,
  StatusRequest,
  StatusResponse,
  TokensRequest,
  TokensResponse,
} from './network.requests';
import {
  validateBalanceRequest as validateEthereumBalanceRequest,
  validateChain as validateEthereumChain,
  validateNetwork as validateEthereumNetwork,
} from '../chains/ethereum/ethereum.validators';
import {
  validateSolanaBalanceRequest,
  validateSolanaPollRequest,
} from '../chains/solana/solana.validators';
import { Rippleish } from '../chains/ripple/ripple';
import {
  validateRippleBalanceRequest,
  validateRipplePollRequest,
} from '../chains/ripple/ripple.validators';
import {
  RippleBalanceResponse,
  RipplePollRequest,
  RipplePollResponse,
} from '../chains/ripple/ripple.requests';

export const validatePollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);

export const validateTokensRequest: RequestValidator = mkRequestValidator([
  validateEthereumChain,
  validateEthereumNetwork,
]);

export namespace NetworkRoutes {
  export const router = Router();

  router.get(
    '/status',
    asyncHandler(
      async (
        req: Request<{}, {}, {}, StatusRequest>,
        res: Response<StatusResponse | StatusResponse[], {}>
      ) => {
        res.status(200).json(await getStatus(req.query));
      }
    )
  );

  router.get('/config', (_req: Request, res: Response<any, any>) => {
    res.status(200).json(ConfigManagerV2.getInstance().allConfigurations);
  });

  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, BalanceRequest>,
        res: Response<BalanceResponse | RippleBalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        let chain: Ethereumish | Solanaish | Rippleish;
        switch (req.body.chain) {
          case 'solana':
            validateSolanaBalanceRequest(req.body);

            chain = await getChain<Solanaish>(req.body.chain, req.body.network);

            res
              .status(200)
              .json(
                (await solanaControllers.balances(
                  chain,
                  req.body
                )) as BalanceResponse
              );
            break;

          case 'ripple':
            validateRippleBalanceRequest(req.body);

            chain = await getChain<Rippleish>(req.body.chain, req.body.network);
            res
              .status(200)
              .json(
                (await rippleControllers.balances(
                  chain,
                  req.body
                )) as RippleBalanceResponse
              );

            break;

          default:
            validateEthereumBalanceRequest(req.body);

            chain = await getChain<Ethereumish>(
              req.body.chain,
              req.body.network
            );

            res
              .status(200)
              .json(await ethereumControllers.balances(chain, req.body));
            break;
        }
      }
    )
  );

  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, PollRequest | RipplePollRequest>,
        res: Response<PollResponse | RipplePollResponse, {}>
      ) => {
        if (req.body.chain == 'solana') {
          validateSolanaPollRequest(req.body);

          const chain = await getChain<Solanaish>(
            req.body.chain,
            req.body.network
          );

          res.status(200).json(await solanaControllers.poll(chain, req.body));
        } else if (req.body.chain == 'ripple') {
          validateRipplePollRequest(req.body);

          const chain = await getChain<Rippleish>(
            req.body.chain,
            req.body.network
          );

          res.status(200).json(await rippleControllers.poll(chain, req.body));
        } else {
          validatePollRequest(req.body);

          const chain = await getChain<Ethereumish>(
            req.body.chain,
            req.body.network
          );

          res.status(200).json(await ethereumControllers.poll(chain, req.body));
        }
      }
    )
  );

  router.get(
    '/tokens',
    asyncHandler(
      async (
        req: Request<{}, {}, {}, TokensRequest>,
        res: Response<TokensResponse, {}>
      ) => {
        validateTokensRequest(req.query);
        res.status(200).json(await getTokens(req.query));
      }
    )
  );
}
