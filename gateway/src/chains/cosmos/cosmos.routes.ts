/* WIP */
/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Router, Request, Response } from 'express';
import { CosmosConfig } from './cosmos.config';
import { verifyCosmosIsAvailable } from './cosmos-middlewares';
import { asyncHandler } from '../../services/error-handler';
import { Cosmos } from './cosmos';
import { balances, poll } from './cosmos.controllers';
import {
  CosmosBalanceResponse,
  CosmosBalanceRequest,
  CosmosPollRequest,
  CosmosPollResponse,
} from './cosmos.requests';
import {
  validateCosmosBalanceRequest,
  validateCosmosPollRequest,
} from './cosmos.validators';

export namespace CosmosRoutes {
  export const router = Router();
  export const cosmos = Cosmos.getInstance('mainnet'); // TODO: make it dynamic

  router.use(asyncHandler(verifyCosmosIsAvailable));

  router.get(
    '/',
    asyncHandler(async (_req: Request, res: Response) => {
      const { rpcUrl } = cosmos;

      res.status(200).json({
        network: CosmosConfig.config.network.name,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  // Get balance for wallet
  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, CosmosBalanceRequest>,
        res: Response<CosmosBalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        validateCosmosBalanceRequest(req.body);
        res.status(200).json(await balances(cosmos, req.body));
      }
    )
  );

  // Gets status information about given transaction hash
  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, CosmosPollRequest>,
        res: Response<CosmosPollResponse, {}>
      ) => {
        validateCosmosPollRequest(req.body);
        res.status(200).json(await poll(cosmos, req.body));
      }
    )
  );
}
