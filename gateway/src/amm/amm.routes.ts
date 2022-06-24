/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';
import { asyncHandler } from '../services/error-handler';
import {
  price,
  trade,
  positionInfo,
  addLiquidity,
  reduceLiquidity,
  collectFees,
  poolPrice,
  estimateGas,
} from './amm.controllers';
import {
  EstimateGasResponse,
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
  AddLiquidityRequest,
  AddLiquidityResponse,
  RemoveLiquidityRequest,
  RemoveLiquidityResponse,
  CollectEarnedFeesRequest,
  PositionRequest,
  PositionResponse,
  PoolPriceRequest,
  PoolPriceResponse,
} from './amm.requests';
import {
  validateEstimateGasRequest,
  validatePriceRequest,
  validateTradeRequest,
  validateAddLiquidityRequest,
  validateRemoveLiquidityRequest,
  validateCollectFeeRequest,
  validatePositionRequest,
  validatePoolPriceRequest,
} from './amm.validators';
import { NetworkSelectionRequest } from '../services/common-interfaces';

export namespace AmmRoutes {
  export const router = Router();

  router.post(
    '/price',
    asyncHandler(
      async (
        req: Request<{}, {}, PriceRequest>,
        res: Response<PriceResponse | string, {}>
      ) => {
        validatePriceRequest(req.body);
        res.status(200).json(await price(req.body));
      }
    )
  );

  router.post(
    '/trade',
    asyncHandler(
      async (
        req: Request<{}, {}, TradeRequest>,
        res: Response<TradeResponse | string, {}>
      ) => {
        validateTradeRequest(req.body);
        res.status(200).json(await trade(req.body));
      }
    )
  );

  router.post(
    '/estimateGas',
    asyncHandler(
      async (
        req: Request<{}, {}, NetworkSelectionRequest>,
        res: Response<EstimateGasResponse | string, {}>
      ) => {
        validateEstimateGasRequest(req.body);
        res.status(200).json(await estimateGas(req.body));
      }
    )
  );
}

export namespace AmmLiquidityRoutes {
  export const router = Router();

  router.post(
    '/position',
    asyncHandler(
      async (
        req: Request<{}, {}, PositionRequest>,
        res: Response<PositionResponse | string, {}>
      ) => {
        validatePositionRequest(req.body);
        res.status(200).json(await positionInfo(req.body));
      }
    )
  );

  router.post(
    '/add',
    asyncHandler(
      async (
        req: Request<{}, {}, AddLiquidityRequest>,
        res: Response<AddLiquidityResponse | string, {}>
      ) => {
        validateAddLiquidityRequest(req.body);
        res.status(200).json(await addLiquidity(req.body));
      }
    )
  );

  router.post(
    '/remove',
    asyncHandler(
      async (
        req: Request<{}, {}, RemoveLiquidityRequest>,
        res: Response<RemoveLiquidityResponse | string, {}>
      ) => {
        validateRemoveLiquidityRequest(req.body);
        res.status(200).json(await reduceLiquidity(req.body));
      }
    )
  );

  router.post(
    '/collect_fees',
    asyncHandler(
      async (
        req: Request<{}, {}, CollectEarnedFeesRequest>,
        res: Response<RemoveLiquidityResponse | string, {}>
      ) => {
        validateCollectFeeRequest(req.body);
        res.status(200).json(await collectFees(req.body));
      }
    )
  );

  router.post(
    '/price',
    asyncHandler(
      async (
        req: Request<{}, {}, PoolPriceRequest>,
        res: Response<PoolPriceResponse | string, {}>
      ) => {
        validatePoolPriceRequest(req.body);
        res.status(200).json(await poolPrice(req.body));
      }
    )
  );
}
