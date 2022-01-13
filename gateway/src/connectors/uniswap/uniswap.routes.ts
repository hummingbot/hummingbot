import { Router, Request, Response } from 'express';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { Uniswap } from './uniswap';
import { asyncHandler } from '../../services/error-handler';
import { verifyEthereumIsAvailable } from '../../chains/ethereum/ethereum-middlewares';
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
import { EthereumConfig } from '../../chains/ethereum/ethereum.config';

export namespace UniswapRoutes {
  export const router = Router();
  export const ethereum = Ethereum.getInstance();
  export const uniswap = Uniswap.getInstance();

  router.use(
    asyncHandler(verifyEthereumIsAvailable),
    asyncHandler(verifyUniswapIsAvailable)
  );

  router.get('/', async (_req: Request, res: Response) => {
    res.status(200).json({
      network: EthereumConfig.config.network.name,
      uniswap_router: uniswap.router,
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
        res.status(200).json(await price(ethereum, uniswap, req.body));
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
        res.status(200).json(await trade(ethereum, uniswap, req.body));
      }
    )
  );
}
