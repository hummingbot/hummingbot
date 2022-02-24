/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Router, Request, Response } from 'express';
import { asyncHandler } from '../services/error-handler';
import { balances, poll } from '../chains/ethereum/ethereum.controllers';
import { getChain } from '../services/connection-manager';
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
  validateBalanceRequest,
  validatePollRequest,
  validateTokensRequest,
} from '../chains/ethereum/ethereum.validators';
import { getStatus, getTokens } from './network.controllers';
import { ConfigManagerV2 } from '../services/config-manager-v2';

export namespace NetworkRoutes {
  export const router = Router();

  router.get(
    '/status',
    async (
      req: Request<{}, {}, {}, StatusRequest>,
      res: Response<StatusResponse, {}>
    ) => {
      try {
        res.status(200).json(await getStatus(req.query));
      } catch (error: any) {
        res.status(error.status).json(error);
      }
    }
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
        validateBalanceRequest(req.body);
        const chain = await getChain(req.body.chain, req.body.network);
        res.status(200).json(await balances(chain, req.body));
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
        validatePollRequest(req.body);
        const chain = await getChain(req.body.chain, req.body.network);
        res.status(200).json(await poll(chain, req.body));
      }
    )
  );

  router.get(
    '/tokens',
    async (
      req: Request<{}, {}, {}, TokensRequest>,
      res: Response<TokensResponse, {}>
    ) => {
      try {
        validateTokensRequest(req.query);
        res.status(200).json(await getTokens(req.query));
      } catch (error: any) {
        res.status(error.status).json(error);
      }
    }
  );
}
