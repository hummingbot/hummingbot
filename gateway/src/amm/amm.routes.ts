/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';
import { asyncHandler } from '../services/error-handler';
import {
  price,
  trade,
  estimateGas,
  estimatePerpGas,
  perpMarketPrices,
  perpOrder,
  getMarketStatus,
  perpPosition,
  perpPairs,
} from './amm.controllers';
import {
  EstimateGasResponse,
  PerpAvailablePairsResponse,
  PerpCreateTakerRequest,
  PerpCreateTakerResponse,
  PerpMarketRequest,
  PerpMarketResponse,
  PerpPositionRequest,
  PerpPositionResponse,
  PerpPricesResponse,
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
} from './amm.requests';
import {
  validateEstimateGasRequest,
  validatePerpCloseTradeRequest,
  validatePerpMarketStatusRequest,
  validatePerpOpenTradeRequest,
  validatePerpPairsRequest,
  validatePerpPositionRequest,
  validatePriceRequest,
  validateTradeRequest,
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

export namespace PerpAmmRoutes {
  export const router = Router();

  router.post(
    '/market-prices',
    asyncHandler(
      async (
        req: Request<{}, {}, PriceRequest>,
        res: Response<PerpPricesResponse | string, {}>
      ) => {
        validatePerpMarketStatusRequest(req.body);
        res.status(200).json(await perpMarketPrices(req.body));
      }
    )
  );

  router.post(
    '/market-status',
    asyncHandler(
      async (
        req: Request<{}, {}, PerpMarketRequest>,
        res: Response<PerpMarketResponse | string, {}>
      ) => {
        validatePerpMarketStatusRequest(req.body);
        res.status(200).json(await getMarketStatus(req.body));
      }
    )
  );

  router.post(
    '/pairs',
    asyncHandler(
      async (
        req: Request<{}, {}, NetworkSelectionRequest>,
        res: Response<PerpAvailablePairsResponse | string, {}>
      ) => {
        validatePerpPairsRequest(req.body);
        res.status(200).json(await perpPairs(req.body));
      }
    )
  );

  router.post(
    '/position',
    asyncHandler(
      async (
        req: Request<{}, {}, PerpPositionRequest>,
        res: Response<PerpPositionResponse | string, {}>
      ) => {
        validatePerpPositionRequest(req.body);
        res.status(200).json(await perpPosition(req.body));
      }
    )
  );

  router.post(
    '/open',
    asyncHandler(
      async (
        req: Request<{}, {}, PerpCreateTakerRequest>,
        res: Response<PerpCreateTakerResponse | string, {}>
      ) => {
        validatePerpOpenTradeRequest(req.body);
        res.status(200).json(await perpOrder(req.body, true));
      }
    )
  );

  router.post(
    '/close',
    asyncHandler(
      async (
        req: Request<{}, {}, PerpCreateTakerRequest>,
        res: Response<PerpCreateTakerResponse | string, {}>
      ) => {
        validatePerpCloseTradeRequest(req.body);
        res.status(200).json(await perpOrder(req.body, false));
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
        res.status(200).json(await estimatePerpGas(req.body));
      }
    )
  );
}
