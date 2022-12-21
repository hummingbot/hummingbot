/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response, NextFunction } from 'express';
import { Nearish } from '../../services/common-interfaces';
import { asyncHandler } from '../../services/error-handler';

import { getChain } from '../../services/connection-manager';
import { BalanceResponse, PollRequest, PollResponse } from './near.requests';
import { validateBalanceRequest } from './near.validators';
import * as nearControllers from './near.controllers';
import { getTokens } from '../../network/network.controllers';
import {
  validatePollRequest,
  validateTokensRequest,
} from '../../network/network.routes';
import {
  BalanceRequest,
  TokensRequest,
  TokensResponse,
} from '../../network/network.requests';

export namespace NearRoutes {
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

        const chain = await getChain<Nearish>('near', req.body.network);

        res
          .status(200)
          .json(
            (await nearControllers.balances(chain, req.body)) as BalanceResponse
          );
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

        const chain = await getChain<Nearish>('near', <string>req.body.network);

        res
          .status(200)
          .json(
            await nearControllers.poll(
              chain,
              <string>req.body.address,
              <string>req.body.txHash
            )
          );
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
