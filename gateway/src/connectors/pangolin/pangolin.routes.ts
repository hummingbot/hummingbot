import { Router, Request, Response, NextFunction } from 'express';
import { asyncHandler } from '../../services/error-handler';
import { price, trade } from '../../../connectors/uniswap/uniswap/uniswap.controllers';

import {
  UniswapPriceRequest,
  UniswapPriceResponse,
  UniswapTradeRequest,
  UniswapTradeResponse,
  UniswapTradeErrorResponse,
} from '../../../connectors/uniswap/uniswap/uniswap.requests';
import {
  validateUniswapPriceRequest,
  validateUniswapTradeRequest,
} from '../../../connectors/uniswap/uniswap/uniswap.validators';
import { Avalanche } from '../../chains/avalanche/avalanche';
import { AvalancheConfig } from '../../chains/avalanche/avalanche.config';
import { Pangolin } from './pangolin';

export namespace PangolinRoutes {
  export const router = Router();
  export const avalanche = Avalanche.getInstance();
  export const pangolin = Pangolin.getInstance();

  router.use(
    asyncHandler(async (_req: Request, _res: Response, next: NextFunction) => {
      if (!avalanche.ready()) {
        await avalanche.init();
      }
      if (!pangolin.ready()) {
        await pangolin.init();
      }
      return next();
    })
  );

  router.get('/', async (_req: Request, res: Response) => {
    res.status(200).json({
      network: AvalancheConfig.config.network.name,
      uniswap_router: pangolin.router,
      connection: true,
      timestamp: Date.now(),
    });
  });

  router.post(
    '/price',
    asyncHandler(
      async (
        req: Request<unknown, unknown, UniswapPriceRequest>,
        res: Response<UniswapPriceResponse, any>
      ) => {
        validateUniswapPriceRequest(req.body);
        res.status(200).json(await price(avalanche, pangolin, req.body));
      }
    )
  );

  router.post(
    '/trade',
    asyncHandler(
      async (
        req: Request<unknown, unknown, UniswapTradeRequest>,
        res: Response<UniswapTradeResponse | UniswapTradeErrorResponse, any>
      ) => {
        validateUniswapTradeRequest(req.body);
        res.status(200).json(await trade(avalanche, pangolin, req.body));
      }
    )
  );
}
