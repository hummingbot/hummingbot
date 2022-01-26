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
} from './network.requests';

import {
  validateBalanceRequest,
  validatePollRequest,
} from '../chains/ethereum/ethereum.validators';

export namespace NetworkRoutes {
  export const router = Router();

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
}
