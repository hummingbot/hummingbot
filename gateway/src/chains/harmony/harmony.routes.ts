/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Router, Request, Response } from 'express';
import { Harmony } from './harmony';
import { HarmonyConfig } from './harmony.config';
import { verifyHarmonyIsAvailable } from './harmony-middlewares';
import { asyncHandler } from '../../services/error-handler';
import {
  approve,
  allowances,
  balances,
  nonce,
  poll,
  cancel,
} from './harmony.controllers';
import {
  HarmonyNonceRequest,
  HarmonyNonceResponse,
  HarmonyAllowancesRequest,
  HarmonyAllowancesResponse,
  HarmonyBalanceRequest,
  HarmonyBalanceResponse,
  HarmonyApproveRequest,
  HarmonyApproveResponse,
  HarmonyPollRequest,
  HarmonyPollResponse,
  HarmonyCancelRequest,
  HarmonyCancelResponse,
} from './harmony.requests';
import {
  validateHarmonyAllowancesRequest,
  validateHarmonyApproveRequest,
  validateHarmonyBalanceRequest,
  validateHarmonyCancelRequest,
  validateHarmonyNonceRequest,
  validateHarmonyPollRequest,
} from './harmony.validators';

export namespace HarmonyRoutes {
  export const router = Router();
  export const harmony = Harmony.getInstance();
  export const reload = (): void => {
    // harmony = Harmony.reload();
  };

  router.use(asyncHandler(verifyHarmonyIsAvailable));

  router.get(
    '/',
    asyncHandler(async (_req: Request, res: Response) => {
      const rpcUrl = HarmonyConfig.config.network.nodeURL;
      res.status(200).json({
        network: HarmonyConfig.config.network,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  router.post(
    '/nonce',
    asyncHandler(
      async (
        req: Request<{}, {}, HarmonyNonceRequest>,
        res: Response<HarmonyNonceResponse | string, {}>
      ) => {
        validateHarmonyNonceRequest(req.body);
        res.status(200).json(await nonce(harmony, req.body));
      }
    )
  );

  router.post(
    '/allowances',
    asyncHandler(
      async (
        req: Request<{}, {}, HarmonyAllowancesRequest>,
        res: Response<HarmonyAllowancesResponse | string, {}>
      ) => {
        validateHarmonyAllowancesRequest(req.body);
        res.status(200).json(await allowances(harmony, req.body));
      }
    )
  );

  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, HarmonyBalanceRequest>,
        res: Response<HarmonyBalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        validateHarmonyBalanceRequest(req.body);
        res.status(200).json(await balances(harmony, req.body));
      }
    )
  );

  router.post(
    '/approve',
    asyncHandler(
      async (
        req: Request<{}, {}, HarmonyApproveRequest>,
        res: Response<HarmonyApproveResponse | string, {}>
      ) => {
        validateHarmonyApproveRequest(req.body);
        return res.status(200).json(await approve(harmony, req.body));
      }
    )
  );

  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, HarmonyPollRequest>,
        res: Response<HarmonyPollResponse, {}>
      ) => {
        validateHarmonyPollRequest(req.body);
        res.status(200).json(await poll(harmony, req.body));
      }
    )
  );

  router.post(
    '/cancel',
    asyncHandler(
      async (
        req: Request<{}, {}, HarmonyCancelRequest>,
        res: Response<HarmonyCancelResponse, {}>
      ) => {
        validateHarmonyCancelRequest(req.body);
        res.status(200).json(await cancel(harmony, req.body));
      }
    )
  );
}
