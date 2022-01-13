/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Router, Request, Response } from 'express';
// import { Ethereum } from './ethereum';
// import { EthereumConfig } from './ethereum.config';
// import { ConfigManager } from '../../services/config-manager';
import { verifyNewEthereumIsAvailable } from '../chains/ethereum/ethereum-middlewares';
import { asyncHandler } from '../services/error-handler';
import {
  approve,
  allowances,
  balances,
  nonce,
  poll,
  cancel,
} from '../chains/ethereum/ethereum.controllers';
import {
  AllowancesRequest,
  AllowancesResponse,
  ApproveRequest,
  BalanceRequest,
  BalanceResponse,
  CancelRequest,
  CancelResponse,
  NonceRequest,
  NonceResponse,
  PollRequest,
  PriceRequest,
  PriceResponse,
  TradeErrorResponse,
  TradeRequest,
  TradeResponse,
} from './trading.requests';
import {
  EthereumApproveResponse,
  EthereumPollResponse,
} from '../chains/ethereum/ethereum.requests';

import {
  validateEthereumAllowancesRequest,
  validateEthereumApproveRequest,
  //   validateEthereumApproveRequest,
  validateEthereumBalanceRequest,
  validateEthereumCancelRequest,
  //   validateEthereumCancelRequest,
  validateEthereumNonceRequest,
  validateEthereumPollRequest,
  //   validateEthereumPollRequest,
} from '../chains/ethereum/ethereum.validators';
import { NewEthereum } from '../chains/ethereum/new_ethereum';
import { price, trade } from '../connectors/uniswap/uniswap.controllers';
import { NewUniswap } from '../connectors/uniswap/new_uniswap';
import { verifyNewUniswapIsAvailable } from '../connectors/uniswap/uniswap-middlewares';
import {
  validatePriceRequest,
  validateTradeRequest,
} from '../connectors/uniswap/uniswap.validators';

export namespace TradingRoutes {
  export const router = Router();

  router.use(asyncHandler(verifyNewEthereumIsAvailable));
  router.use(asyncHandler(verifyNewUniswapIsAvailable));

  router.post(
    '/nonce',
    asyncHandler(
      async (
        req: Request<{}, {}, NonceRequest>,
        res: Response<NonceResponse | string, {}>
      ) => {
        if (req.body.chain == 'ethereum') {
          validateEthereumNonceRequest(req.body);
          const ethereum = NewEthereum.getInstance(req.body.network);
          res.status(200).json(await nonce(ethereum, req.body));
        }
      }
    )
  );

  router.post(
    '/allowances',
    asyncHandler(
      async (
        req: Request<{}, {}, AllowancesRequest>,
        res: Response<AllowancesResponse | string, {}>
      ) => {
        if (req.body.chain == 'ethereum') {
          validateEthereumAllowancesRequest(req.body);
          const ethereum = NewEthereum.getInstance(req.body.network);
          res.status(200).json(await allowances(ethereum, req.body));
        }
      }
    )
  );

  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, BalanceRequest>,
        res: Response<BalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        if (req.body.chain == 'ethereum') {
          validateEthereumBalanceRequest(req.body);
          const ethereum = NewEthereum.getInstance(req.body.network);
          res.status(200).json(await balances(ethereum, req.body));
        }
      }
    )
  );

  router.post(
    '/approve',
    asyncHandler(
      async (
        req: Request<{}, {}, ApproveRequest>,
        res: Response<EthereumApproveResponse | string, {}>
      ) => {
        validateEthereumApproveRequest(req.body);
        const ethereum = NewEthereum.getInstance(req.body.network);
        return res.status(200).json(await approve(ethereum, req.body));
      }
    )
  );

  router.post(
    '/price',
    asyncHandler(
      async (
        req: Request<unknown, unknown, PriceRequest>,
        res: Response<PriceResponse, any>
      ) => {
        // validateUniswapPriceRequest(req.body);
        if (req.body.connector == 'uniswap' && req.body.chain == 'ethereum') {
          validateUniswapPriceRequest(req.body);
          const ethereum = NewEthereum.getInstance(req.body.network);
          const uniswap = NewUniswap.getInstance(
            req.body.chain,
            req.body.network
          );
          res.status(200).json(await price(ethereum, uniswap, req.body));
        }
      }
    )
  );

  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, PollRequest>,
        res: Response<EthereumPollResponse, {}>
      ) => {
        if (req.body.chain == 'ethereum') {
          const ethereum = NewEthereum.getInstance(req.body.network);
          validateEthereumPollRequest(req.body);
          res.status(200).json(await poll(ethereum, req.body));
        }
      }
    )
  );

  router.post(
    '/cancel',
    asyncHandler(
      async (
        req: Request<{}, {}, CancelRequest>,
        res: Response<CancelResponse, {}>
      ) => {
        if (req.body.chain == 'ethereum') {
          const ethereum = NewEthereum.getInstance(req.body.network);
          validateEthereumCancelRequest(req.body);
          res.status(200).json(await cancel(ethereum, req.body));
        }
      }
    )
  );

  router.post(
    '/trade',
    asyncHandler(
      async (
        req: Request<unknown, unknown, TradeRequest>,
        res: Response<TradeResponse | TradeErrorResponse, any>
      ) => {
        validateTradeRequest(req.body);
        if (req.body.connector == 'uniswap' && req.body.chain == 'ethereum') {
          const ethereum = NewEthereum.getInstance(req.body.network);
          const uniswap = NewUniswap.getInstance(
            req.body.chain,
            req.body.network
          );
          res.status(200).json(await trade(ethereum, uniswap, req.body));
        }
      }
    )
  );
}
