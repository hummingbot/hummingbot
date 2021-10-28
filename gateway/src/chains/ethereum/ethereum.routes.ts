/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Router, Request, Response } from 'express';
import { Ethereum } from './ethereum';
import { EthereumConfig } from './ethereum.config';
import { ConfigManager } from '../../services/config-manager';
import { verifyEthereumIsAvailable } from './ethereum-middlewares';
import { asyncHandler } from '../../services/error-handler';
import {
  approve,
  allowances,
  balances,
  nonce,
  poll,
  cancel,
} from './ethereum.controllers';
import {
  EthereumNonceRequest,
  EthereumNonceResponse,
  EthereumAllowancesRequest,
  EthereumAllowancesResponse,
  EthereumBalanceRequest,
  EthereumBalanceResponse,
  EthereumApproveRequest,
  EthereumApproveResponse,
  EthereumPollRequest,
  EthereumPollResponse,
  EthereumCancelRequest,
  EthereumCancelResponse,
} from './ethereum.requests';
import {
  validateEthereumAllowancesRequest,
  validateEthereumApproveRequest,
  validateEthereumBalanceRequest,
  validateEthereumCancelRequest,
  validateEthereumNonceRequest,
  validateEthereumPollRequest,
} from './ethereum.validators';

export namespace EthereumRoutes {
  export const router = Router();
  export const ethereum = Ethereum.getInstance();
  export const reload = (): void => {
    // ethereum = Ethereum.reload();
  };

  router.use(asyncHandler(verifyEthereumIsAvailable));

  router.get(
    '/',
    asyncHandler(async (_req: Request, res: Response) => {
      let rpcUrl;
      if (ConfigManager.config.ETHEREUM_CHAIN === 'mainnet') {
        rpcUrl = EthereumConfig.config.mainnet.rpcUrl;
      } else {
        rpcUrl = EthereumConfig.config.kovan.rpcUrl;
      }

      res.status(200).json({
        network: ConfigManager.config.ETHEREUM_CHAIN,
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
        validateEthereumNonceRequest(req.body);
        res.status(200).json(await nonce(ethereum, req.body));
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
        validateEthereumAllowancesRequest(req.body);
        res.status(200).json(await allowances(ethereum, req.body));
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
        validateEthereumBalanceRequest(req.body);
        res.status(200).json(await balances(ethereum, req.body));
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
        validateEthereumApproveRequest(req.body);
        return res.status(200).json(await approve(ethereum, req.body));
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
        validateEthereumPollRequest(req.body);
        res.status(200).json(await poll(ethereum, req.body));
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
        validateEthereumCancelRequest(req.body);
        res.status(200).json(await cancel(ethereum, req.body));
      }
    )
  );
}
