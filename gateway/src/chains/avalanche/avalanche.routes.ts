/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Router, Request, Response } from 'express';
import { AvalancheConfig } from './avalanche.config';
import { ConfigManager } from '../../services/config-manager';
import { asyncHandler } from '../../services/error-handler';
import { Avalanche } from './avalanche';
import {
  EthereumAllowancesRequest,
  EthereumAllowancesResponse,
  EthereumApproveRequest,
  EthereumApproveResponse,
  EthereumBalanceRequest,
  EthereumBalanceResponse,
  EthereumCancelRequest,
  EthereumCancelResponse,
  EthereumNonceRequest,
  EthereumNonceResponse,
  EthereumPollRequest,
  EthereumPollResponse,
} from '../ethereum/ethereum.requests';
import {
  allowances,
  approve,
  balances,
  cancel,
  nonce,
  poll,
} from '../ethereum/ethereum.controllers';

export namespace AvalancheRoutes {
  export const router = Router();
  export const avalanche = Avalanche.getInstance();
  export const reload = (): void => {
    // avalanche = Avalanche.reload();
  };

  router.use(
    asyncHandler(async (_req: Request, _res: Response, next: NextFunction) => {
      if (!avalanche.ready()) {
        await avalanche.init();
      }
      return next();
    })
  );

  router.get(
    '/',
    asyncHandler(async (_req: Request, res: Response) => {
      let rpcUrl;
      if (ConfigManager.config.AVALANCHE_CHAIN === 'avalanche') {
        rpcUrl = AvalancheConfig.config.avalanche.rpcUrl;
      } else {
        rpcUrl = AvalancheConfig.config.fuji.rpcUrl;
      }

      res.status(200).json({
        network: ConfigManager.config.AVALANCHE_CHAIN,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  router.post(
    '/nonce',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumNonceRequest>,
        res: Response<EthereumNonceResponse | string, {}>
      ) => {
        res.status(200).json(await nonce(avalanche, req.body));
      }
    )
  );

  router.post(
    '/allowances',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumAllowancesRequest>,
        res: Response<EthereumAllowancesResponse | string, {}>
      ) => {
        res.status(200).json(await allowances(avalanche, req.body));
      }
    )
  );

  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumBalanceRequest>,
        res: Response<EthereumBalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        res.status(200).json(await balances(avalanche, req.body));
      }
    )
  );

  router.post(
    '/approve',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumApproveRequest>,
        res: Response<EthereumApproveResponse | string, {}>
      ) => {
        return res.status(200).json(await approve(avalanche, req.body));
      }
    )
  );

  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumPollRequest>,
        res: Response<EthereumPollResponse, {}>
      ) => {
        res.status(200).json(await poll(avalanche, req.body));
      }
    )
  );

  router.post(
    '/cancel',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumCancelRequest>,
        res: Response<EthereumCancelResponse, {}>
      ) => {
        res.status(200).json(await cancel(avalanche, req.body));
      }
    )
  );
}
