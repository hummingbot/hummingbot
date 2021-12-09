import { Router, Request, Response } from 'express';
import { Solana } from '../solana';
import { Mango } from './mango';
import { ConfigManager } from '../../../services/config-manager';
import { asyncHandler } from '../../../services/error-handler';
import { verifySolanaIsAvailable } from '../solana-middlewares';
import { verifyMangoIsAvailable } from './mango-middlewares';
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
  export const mango = Mango.getInstance();
  export const solana = Solana.getInstance();

  router.use(
    asyncHandler(verifySolanaIsAvailable),
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
