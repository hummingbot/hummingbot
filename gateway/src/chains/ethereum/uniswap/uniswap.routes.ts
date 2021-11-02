import { Router, Request, Response } from 'express';
import { Ethereum } from '../ethereum';
import { Uniswap } from './uniswap';
import { ConfigManager } from '../../../services/config-manager';
import { asyncHandler } from '../../../services/error-handler';
import { verifyEthereumIsAvailable } from '../ethereum-middlewares';
import { verifyUniswapIsAvailable } from './uniswap-middlewares';
import { price, trade } from './uniswap.controllers';

import {
  UniswapPriceRequest,
  UniswapPriceResponse,
  UniswapTradeRequest,
  UniswapTradeResponse,
  UniswapTradeErrorResponse,
} from './uniswap.requests';
import {
  validateUniswapPriceRequest,
  validateUniswapTradeRequest,
} from './uniswap.validators';

export namespace UniswapRoutes {
  export const router = Router();
  export const uniswap = Uniswap.getInstance();
  export const ethereum = Ethereum.getInstance();

  router.use(
    asyncHandler(verifyEthereumIsAvailable),
    asyncHandler(verifyUniswapIsAvailable)
  );

  router.get('/', async (_req: Request, res: Response) => {
    res.status(200).json({
      network: ConfigManager.config.ETHEREUM_CHAIN,
      uniswap_router: uniswap.uniswapRouter,
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
        res.status(200).json(await price(req.body));
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
        res.status(200).json(await trade(req.body));
      }
    )
  );
}
