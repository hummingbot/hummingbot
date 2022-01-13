/* eslint-disable no-inner-declarations */
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
  validateAllowancesRequest,
  validateApproveRequest,
  //   validateEthereumApproveRequest,
  validateBalanceRequest,
  validateCancelRequest,
  //   validateEthereumCancelRequest,
  validateNonceRequest,
  validatePollRequest,
  //   validateEthereumPollRequest,
} from '../chains/ethereum/ethereum.validators';
import { NewEthereum } from '../chains/ethereum/new_ethereum';
import { NewAvalanche } from '../chains/avalanche/new_avalanche';
import { price, trade } from '../connectors/uniswap/uniswap.controllers';
import { NewUniswap } from '../connectors/uniswap/new_uniswap';
import { NewPangolin } from '../connectors/pangolin/new_pangolin';
import { verifyNewUniswapIsAvailable } from '../connectors/uniswap/uniswap-middlewares';
import {
  validatePriceRequest,
  validateTradeRequest,
} from '../connectors/uniswap/uniswap.validators';

export namespace TradingRoutes {
  export const router = Router();

  router.use(asyncHandler(verifyNewEthereumIsAvailable));
  router.use(asyncHandler(verifyNewUniswapIsAvailable));

  function getChain(chain: string, network: string) {
    if (chain === 'ethereum') return NewEthereum.getInstance(network);
    else if (chain === 'avalanche') return NewAvalanche.getInstance(network);
    else throw new Error('unsupported chain');
  }

  function getConnector(chain: string, network: string, connector: string) {
    if (chain === 'ethereum' && connector === 'uniswap')
      return NewUniswap.getInstance(chain, network);
    else if (chain === 'avalanche' && connector === 'pangolin')
      return NewPangolin.getInstance(chain, network);
    else throw new Error('unsupported chain or network');
  }

  router.post(
    '/nonce',
    asyncHandler(
      async (
        req: Request<{}, {}, NonceRequest>,
        res: Response<NonceResponse | string, {}>
      ) => {
        validateNonceRequest(req.body);
        const chain = getChain(req.body.chain, req.body.network);
        res.status(200).json(await nonce(chain, req.body));
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
        validateAllowancesRequest(req.body);
        const chain = getChain(req.body.chain, req.body.network);
        res.status(200).json(await allowances(chain, req.body));
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
        validateBalanceRequest(req.body);
        const chain = getChain(req.body.chain, req.body.network);
        res.status(200).json(await balances(chain, req.body));
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
        validateApproveRequest(req.body);
        const chain = getChain(req.body.chain, req.body.network);
        res.status(200).json(await approve(chain, req.body));
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
        validatePriceRequest(req.body);
        const chain = getChain(req.body.chain, req.body.network);
        const connector = getConnector(
          req.body.chain,
          req.body.network,
          req.body.connector
        );
        res.status(200).json(await price(chain, connector, req.body));
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
        validatePollRequest(req.body);
        const chain = getChain(req.body.chain, req.body.network);
        res.status(200).json(await poll(chain, req.body));
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
          validateCancelRequest(req.body);
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
        const chain = getChain(req.body.chain, req.body.network);
        const connector = getConnector(
          req.body.chain,
          req.body.network,
          req.body.connector
        );
        res.status(200).json(await trade(chain, connector, req.body));
      }
    )
  );
}
