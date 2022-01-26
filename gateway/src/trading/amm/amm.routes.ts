/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';
import { asyncHandler } from '../../services/error-handler';
import { price } from './amm.controllers';
import { PriceRequest, PriceResponse } from './amm.requests';
import { validatePriceRequest } from './amm.validators';

export namespace AmmRoutes {
  export const router = Router();

  // price
  // trade
  // liquidity add
  // liquidity remove

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
}
