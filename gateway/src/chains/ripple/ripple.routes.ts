import { NextFunction, Request, Response, Router } from 'express';
import { ParamsDictionary } from 'express-serve-static-core';
import { Ripple } from './ripple';
import { verifySolanaIsAvailable } from './ripple-middlewares';
import { asyncHandler } from '../../services/error-handler';
import {
  balances,
  getOrCreateTokenAccount,
  poll,
  token,
} from './ripple.controllers';
import {
  RippleBalanceRequest,
  RippleBalanceResponse,
  SolanaPollRequest,
  SolanaPollResponse,
  RippleTokenRequest,
  RippleTokenResponse,
} from './ripple.requests';
import {
  validateSolanaBalanceRequest,
  validateSolanaGetTokenRequest,
  validateSolanaPollRequest,
  validateSolanaPostTokenRequest,
} from './ripple.validators';

export namespace SolanaRoutes {
  export const router = Router();

  export const getSolana = async (request: Request) => {
    const solana = await Ripple.getInstance(request.body.network);
    await solana.init();

    return solana;
  };

  router.use(asyncHandler(verifySolanaIsAvailable));

  router.get(
    '/',
    asyncHandler(async (request: Request, response: Response) => {
      const solana = await getSolana(request);

      const rpcUrl = solana.rpcUrl;

      response.status(200).json({
        network: solana.network,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  // Get all token accounts and balances + solana balance
  router.get(
    '/balances',
    asyncHandler(
      async (
        request: Request<ParamsDictionary, unknown, RippleBalanceRequest>,
        response: Response<RippleBalanceResponse | string>,
        _next: NextFunction
      ) => {
        const solana = await getSolana(request);

        validateSolanaBalanceRequest(request.body);
        response.status(200).json(await balances(solana, request.body));
      }
    )
  );

  // Checks whether this specific token account exists and returns its balance, if it does.
  router.get(
    '/token',
    asyncHandler(
      async (
        request: Request<ParamsDictionary, unknown, RippleTokenRequest>,
        response: Response<RippleTokenResponse | string>,
        _next: NextFunction
      ) => {
        const solana = await getSolana(request);

        validateSolanaGetTokenRequest(request.body);
        response.status(200).json(await token(solana, request.body));
      }
    )
  );

  // Creates a new associated token account, if not existent
  router.post(
    '/token',
    asyncHandler(
      async (
        request: Request<ParamsDictionary, unknown, RippleTokenRequest>,
        response: Response<RippleTokenResponse | string>,
        _next: NextFunction
      ) => {
        const solana = await getSolana(request);

        validateSolanaPostTokenRequest(request.body);
        response
          .status(200)
          .json(await getOrCreateTokenAccount(solana, request.body));
      }
    )
  );

  // TODO Check the possibility to change to a GET method (consider the Ethereum implementation)
  // Gets status information about given transaction hash
  router.post(
    '/poll',
    asyncHandler(
      async (
        request: Request<ParamsDictionary, unknown, SolanaPollRequest>,
        response: Response<SolanaPollResponse>
      ) => {
        const solana = await getSolana(request);

        validateSolanaPollRequest(request.body);
        response.status(200).json(await poll(solana, request.body));
      }
    )
  );
}
