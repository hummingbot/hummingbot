/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Router, Request, Response } from 'express';
// import { Ethereum } from './ethereum';
// import { EthereumConfig } from './ethereum.config';
// import { ConfigManager } from '../../services/config-manager';
// import { verifyNewEthereumIsAvailable } from '../chains/ethereum/ethereum-middlewares';
// import { verifyNewAvalancheIsAvailable } from '../chains/avalanche/avalanche-middlewares';
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
// import { verifyNewUniswapIsAvailable } from '../connectors/uniswap/uniswap-middlewares';
import {
  validatePriceRequest,
  validateTradeRequest,
} from '../connectors/uniswap/uniswap.validators';
import { Ethereumish } from '../services/ethereumish.interface';

export namespace TradingRoutes {
  export const router = Router();

  // router.use(asyncHandler(verifyNewEthereumIsAvailable));
  // // router.use(asyncHandler(verifyNewAvalancheIsAvailable));
  // router.use(asyncHandler(verifyNewUniswapIsAvailable));

  async function getChain(chain: string, network: string) {
    let chainInstance: Ethereumish;
    if (chain === 'ethereum') chainInstance = NewEthereum.getInstance(network);
    else if (chain === 'avalanche')
      chainInstance = NewAvalanche.getInstance(network);
    else throw new Error('unsupported chain');
    if (!chainInstance.ready()) {
      await chainInstance.init();
    }
    return chainInstance;
  }

  async function getConnector(
    chain: string,
    network: string,
    connector: string
  ) {
    let connectorInstance: any;
    if (chain === 'ethereum' && connector === 'uniswap')
      connectorInstance = NewUniswap.getInstance(chain, network);
    else if (chain === 'avalanche' && connector === 'pangolin')
      connectorInstance = NewPangolin.getInstance(chain, network);
    else throw new Error('unsupported chain or connector');
    if (!connectorInstance.ready()) {
      await connectorInstance.init();
    }
    return connectorInstance;
  }

  router.post(
    '/nonce',
    asyncHandler(
      async (
        req: Request<{}, {}, NonceRequest>,
        res: Response<NonceResponse | string, {}>
      ) => {
        validateNonceRequest(req.body);
        const chain = await getChain(req.body.chain, req.body.network);
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
        const chain = await getChain(req.body.chain, req.body.network);
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
        const chain = await getChain(req.body.chain, req.body.network);
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
        const chain = await getChain(req.body.chain, req.body.network);
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
        const chain = await getChain(req.body.chain, req.body.network);
        const connector = await getConnector(
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
        console.log('validate');
        validatePollRequest(req.body);
        console.log('get chain');
        const chain = await getChain(req.body.chain, req.body.network);
        console.log('poll');
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
        validateCancelRequest(req.body);
        const chain = await getChain(req.body.chain, req.body.network);
        res.status(200).json(await cancel(chain, req.body));
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
        const chain = await getChain(req.body.chain, req.body.network);
        const connector = await getConnector(
          req.body.chain,
          req.body.network,
          req.body.connector
        );
        res.status(200).json(await trade(chain, connector, req.body));
      }
    )
  );
}
