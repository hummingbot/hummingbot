/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Request, Response, Router } from 'express';
import * as ethereumControllers from '../chains/ethereum/ethereum.controllers';
import { Solanaish } from '../chains/solana/solana';
import * as solanaControllers from '../chains/solana/solana.controllers';
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
        res: Response<BalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        if (req.body.chain == 'solana') {
          validateSolanaBalanceRequest(req.body);

          const chain = await getChain<Solanaish>(
            req.body.chain,
            req.body.network
          );

          res
            .status(200)
            .json(
              (await solanaControllers.balances(
                chain,
                req.body
              )) as BalanceResponse
            );
        } else {
          validateEthereumBalanceRequest(req.body);

          const chain = await getChain<Ethereumish>(
            req.body.chain,
            req.body.network
          );

          res
            .status(200)
            .json(await ethereumControllers.balances(chain, req.body));
        }
      }
    )
  );

  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, PollRequest>,
        res: Response<PollResponse, {}>
      ) => {
        if (req.body.chain == 'solana') {
          validateSolanaPollRequest(req.body);

          const chain = await getChain<Solanaish>(
            req.body.chain,
            req.body.network
          );

          res.status(200).json(await solanaControllers.poll(chain, req.body));
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
