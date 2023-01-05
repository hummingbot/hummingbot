/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Request, Response, Router } from 'express';
import * as ethereumControllers from '../chains/ethereum/ethereum.controllers';
import { Solanaish } from '../chains/solana/solana';
import * as solanaControllers from '../chains/solana/solana.controllers';
import * as xrplControllers from '../chains/xrpl/xrpl.controllers';
import { Ethereumish } from '../services/common-interfaces';
import { ConfigManagerV2 } from '../services/config-manager-v2';
import { getChain } from '../services/connection-manager';
import { asyncHandler } from '../services/error-handler';
import {
  mkRequestValidator,
  RequestValidator,
  validateTxHash,
} from '../services/validators';
import { getStatus, getTokens } from './network.controllers';
import {
  BalanceRequest,
  BalanceResponse,
  PollRequest,
  PollResponse,
  StatusRequest,
  StatusResponse,
  TokensRequest,
  TokensResponse,
} from './network.requests';
import {
  validateBalanceRequest as validateEthereumBalanceRequest,
  validateChain as validateEthereumChain,
  validateNetwork as validateEthereumNetwork,
} from '../chains/ethereum/ethereum.validators';
import {
  validateSolanaBalanceRequest,
  validateSolanaPollRequest,
} from '../chains/solana/solana.validators';
import { XRPLish } from '../chains/xrpl/xrpl';
import {
  validateXRPLBalanceRequest,
  validateXRPLPollRequest,
} from '../chains/xrpl/xrpl.validators';
import {
  XRPLBalanceResponse,
  XRPLPollRequest,
  XRPLPollResponse,
} from '../chains/xrpl/xrpl.requests';

export const validatePollRequest: RequestValidator = mkRequestValidator([
  validateTxHash,
]);

export const validateTokensRequest: RequestValidator = mkRequestValidator([
  validateEthereumChain,
  validateEthereumNetwork,
]);

export namespace NetworkRoutes {
  export const router = Router();

  router.get(
    '/status',
    asyncHandler(
      async (
        req: Request<{}, {}, {}, StatusRequest>,
        res: Response<StatusResponse | StatusResponse[], {}>
      ) => {
        res.status(200).json(await getStatus(req.query));
      }
    )
  );

  router.get('/config', (_req: Request, res: Response<any, any>) => {
    res.status(200).json(ConfigManagerV2.getInstance().allConfigurations);
  });

  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, BalanceRequest>,
        res: Response<BalanceResponse | XRPLBalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        let chain: Ethereumish | Solanaish | XRPLish;
        switch (req.body.chain) {
          case 'solana':
            validateSolanaBalanceRequest(req.body);

            chain = await getChain<Solanaish>(req.body.chain, req.body.network);

            res
              .status(200)
              .json(
                (await solanaControllers.balances(
                  chain,
                  req.body
                )) as BalanceResponse
              );
            break;

          case 'xrpl':
            validateXRPLBalanceRequest(req.body);

            chain = await getChain<XRPLish>(req.body.chain, req.body.network);
            res
              .status(200)
              .json(
                (await xrplControllers.balances(
                  chain,
                  req.body
                )) as XRPLBalanceResponse
              );

            break;

          default:
            validateEthereumBalanceRequest(req.body);

            chain = await getChain<Ethereumish>(
              req.body.chain,
              req.body.network
            );

            res
              .status(200)
              .json(await ethereumControllers.balances(chain, req.body));
            break;
        }
      }
    )
  );

  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, PollRequest | XRPLPollRequest>,
        res: Response<PollResponse | XRPLPollResponse, {}>
      ) => {
        if (req.body.chain == 'solana') {
          validateSolanaPollRequest(req.body);

          const chain = await getChain<Solanaish>(
            req.body.chain,
            req.body.network
          );

          res.status(200).json(await solanaControllers.poll(chain, req.body));
        } else if (req.body.chain == 'xrpl') {
          validateXRPLPollRequest(req.body);

          const chain = await getChain<XRPLish>(
            req.body.chain,
            req.body.network
          );

          res.status(200).json(await xrplControllers.poll(chain, req.body));
        } else {
          validatePollRequest(req.body);

          const chain = await getChain<Ethereumish>(
            req.body.chain,
            req.body.network
          );

          res.status(200).json(await ethereumControllers.poll(chain, req.body));
        }
      }
    )
  );

  router.get(
    '/tokens',
    asyncHandler(
      async (
        req: Request<{}, {}, {}, TokensRequest>,
        res: Response<TokensResponse, {}>
      ) => {
        validateTokensRequest(req.query);
        res.status(200).json(await getTokens(req.query));
      }
    )
  );
}
