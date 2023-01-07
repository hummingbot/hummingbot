/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';
import { asyncHandler } from '../../services/error-handler';
import {
  balances,
  currentBlockNumber,
  poll,
  transferToBankAccount,
  transferToSubAccount,
} from './injective.controllers';
import { Injective } from './injective';
import {
  BalancesRequest,
  BalancesResponse,
  PollRequest,
  PollResponse,
  TransferToBankAccountRequest,
  TransferToBankAccountResponse,
  TransferToSubAccountRequest,
  TransferToSubAccountResponse,
} from './injective.requests';
import {
  validatePollRequest,
  validateBalanceRequest,
  validateTransferToBankAccountRequest,
  validateTransferToSubAccountRequest,
} from './injective.validators';
import { getChain } from '../../services/connection-manager';
import { NetworkSelectionRequest } from '../../services/common-interfaces';

export namespace InjectiveRoutes {
  export const router = Router();

  router.get(
    '/block/current',
    asyncHandler(
      async (
        req: Request<{}, {}, NetworkSelectionRequest>,
        res: Response<number, {}>
      ) => {
        const injective = await getChain(
          <string>req.query.chain,
          <string>req.query.network
        );
        res.status(200).json(await currentBlockNumber(<Injective>injective));
      }
    )
  );

  router.post(
    '/transfer/to/bank',
    asyncHandler(
      async (
        req: Request<{}, {}, TransferToBankAccountRequest>,
        res: Response<TransferToBankAccountResponse, {}>
      ) => {
        validateTransferToBankAccountRequest(req.body);
        const injective = await getChain(
          <string>req.body.chain,
          <string>req.body.network
        );
        res
          .status(200)
          .json(await transferToBankAccount(<Injective>injective, req.body));
      }
    )
  );

  router.post(
    '/transfer/to/sub',
    asyncHandler(
      async (
        req: Request<{}, {}, TransferToSubAccountRequest>,
        res: Response<TransferToSubAccountResponse, {}>
      ) => {
        validateTransferToSubAccountRequest(req.body);
        const injective = await getChain(
          <string>req.body.chain,
          <string>req.body.network
        );
        res
          .status(200)
          .json(await transferToSubAccount(<Injective>injective, req.body));
      }
    )
  );

  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, BalancesRequest>,
        res: Response<BalancesResponse, {}>
      ) => {
        validateBalanceRequest(req.body);
        const injective = await getChain(
          <string>req.body.chain,
          <string>req.body.network
        );
        res.status(200).json(await balances(<Injective>injective, req.body));
      }
    )
  );

  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, PollRequest>,
        res: Response<PollResponse, {}>
      ) => {
        validatePollRequest(req.body);
        const injective = await getChain(
          <string>req.body.chain,
          <string>req.body.network
        );
        res.status(200).json(await poll(<Injective>injective, req.body));
      }
    )
  );
}
