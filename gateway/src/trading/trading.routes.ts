/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';
import { asyncHandler } from '../services/error-handler';
import {
  PriceRequest,
  PriceResponse,
  TradeErrorResponse,
  TradeRequest,
  TradeResponse,
} from './trading.requests';

import { price, trade } from '../connectors/uniswap/uniswap.controllers';

import {
  validatePriceRequest,
  validateTradeRequest,
} from '../connectors/uniswap/uniswap.validators';
import { getChain, getConnector } from '../services/connection-manager';

export namespace TradingRoutes {
  export const router = Router();

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
          req.body.connector || ''
        );
        res.status(200).json(await price(chain, connector, req.body));
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
          req.body.connector || ''
        );
        res.status(200).json(await trade(chain, connector, req.body));
      }
    )
  );
}
