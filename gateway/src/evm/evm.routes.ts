/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';
import { Ethereumish } from '../services/common-interfaces';
import { asyncHandler } from '../services/error-handler';
import {
  approve,
  allowances,
  nonce,
  nextNonce,
  cancel,
} from '../chains/ethereum/ethereum.controllers';

import {
  validateAllowancesRequest,
  validateApproveRequest,
  validateCancelRequest,
  validateNonceRequest,
} from '../chains/ethereum/ethereum.validators';
import { getChain } from '../services/connection-manager';
import {
  AllowancesRequest,
  AllowancesResponse,
  ApproveRequest,
  ApproveResponse,
  CancelRequest,
  CancelResponse,
  NonceRequest,
  NonceResponse,
} from './evm.requests';

export namespace EVMRoutes {
  export const router = Router();

  router.post(
    '/nextNonce',
    asyncHandler(
      async (
        req: Request<{}, {}, NonceRequest>,
        res: Response<NonceResponse | string, {}>
      ) => {
        validateNonceRequest(req.body);
        const chain = await getChain<Ethereumish>(
          req.body.chain,
          req.body.network
        );
        res.status(200).json(await nextNonce(chain, req.body));
      }
    )
  );

  router.post(
    '/nonce',
    asyncHandler(
      async (
        req: Request<{}, {}, NonceRequest>,
        res: Response<NonceResponse | string, {}>
      ) => {
        validateNonceRequest(req.body);
        const chain = await getChain<Ethereumish>(
          req.body.chain,
          req.body.network
        );
        res.status(200).json(await nonce(chain, req.body));
      }
    )
  );

  router.post(
    '/allowances',
    asyncHandler(
      async (
        req: Request<{}, {}, AllowancesRequest>,
        res: Response<AllowancesResponse | string, {}>
      ) => {
        validateAllowancesRequest(req.body);
        const chain = await getChain<Ethereumish>(
          req.body.chain,
          req.body.network
        );
        res.status(200).json(await allowances(chain, req.body));
      }
    )
  );

  router.post(
    '/approve',
    asyncHandler(
      async (
        req: Request<{}, {}, ApproveRequest>,
        res: Response<ApproveResponse | string, {}>
      ) => {
        validateApproveRequest(req.body);
        const chain = await getChain<Ethereumish>(
          req.body.chain,
          req.body.network
        );
        res.status(200).json(await approve(chain, req.body));
      }
    )
  );

  router.post(
    '/cancel',
    asyncHandler(
      async (
        req: Request<{}, {}, CancelRequest>,
        res: Response<CancelResponse, {}>
      ) => {
        validateCancelRequest(req.body);
        const chain = await getChain<Ethereumish>(
          req.body.chain,
          req.body.network
        );
        res.status(200).json(await cancel(chain, req.body));
      }
    )
  );
}
