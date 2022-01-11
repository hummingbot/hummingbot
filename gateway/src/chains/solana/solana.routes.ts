/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Router, Request, Response } from 'express';
import { Solana } from './solana';
import { SolanaConfig } from './solana.config';
import { verifySolanaIsAvailable } from './solana-middlewares';
import { asyncHandler } from '../../services/error-handler';
import {
  token,
  balances,
  poll,
  getOrCreateTokenAccount,
} from './solana.controllers';
import {
  SolanaBalanceRequest,
  SolanaBalanceResponse,
  SolanaPollRequest,
  SolanaPollResponse,
  SolanaTokenResponse,
  SolanaTokenRequest,
} from './solana.requests';
import {
  validateSolanaGetTokenRequest,
  validateSolanaBalanceRequest,
  validateSolanaPostTokenRequest,
  validateSolanaPollRequest,
} from './solana.validators';

export namespace SolanaRoutes {
  export const router = Router();
  export const solana = Solana.getInstance();
  export const reload = (): void => {
    // Solana = Solana.reload();
  };

  router.use(asyncHandler(verifySolanaIsAvailable));

  router.get(
    '/',
    asyncHandler(async (_req: Request, res: Response) => {
      const rpcUrl = solana.rpcUrl;

      res.status(200).json({
        network: SolanaConfig.config.network.slug,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  // Get all token accounts and balances + solana balance
  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, SolanaBalanceRequest>,
        res: Response<SolanaBalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        validateSolanaBalanceRequest(req.body);
        res.status(200).json(await balances(solana, req.body));
      }
    )
  );

  // Checks whether this specific token account exists and returns it balance, if it does.
  router.get(
    '/token',
    asyncHandler(
      async (
        req: Request<{}, {}, SolanaTokenRequest>,
        res: Response<SolanaTokenResponse | string, {}>,
        _next: NextFunction
      ) => {
        validateSolanaGetTokenRequest(req.body);
        res.status(200).json(await token(solana, req.body));
      }
    )
  );

  // Creates a new associated token account, if not existent
  router.post(
    '/token',
    asyncHandler(
      async (
        req: Request<{}, {}, SolanaTokenRequest>,
        res: Response<SolanaTokenResponse | string, {}>,
        _next: NextFunction
      ) => {
        validateSolanaPostTokenRequest(req.body);
        res.status(200).json(await getOrCreateTokenAccount(solana, req.body));
      }
    )
  );

  // Gets status information about given transaction hash
  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, SolanaPollRequest>,
        res: Response<SolanaPollResponse, {}>
      ) => {
        validateSolanaPollRequest(req.body);
        res.status(200).json(await poll(solana, req.body));
      }
    )
  );
}
