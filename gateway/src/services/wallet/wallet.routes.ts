/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';

import { asyncHandler } from '../error-handler';

import { addWallet, removeWallet, getWallets } from './wallet.controllers';

import {
  AddWalletRequest,
  AddWalletResponse,
  RemoveWalletRequest,
  GetWalletResponse,
} from './wallet.requests';

import {
  validateAddWalletRequest,
  validateRemoveWalletRequest,
} from './wallet.validators';

export namespace WalletRoutes {
  export const router = Router();

  router.get(
    '/',
    asyncHandler(async (_req, res: Response<GetWalletResponse[], {}>) => {
      const response = await getWallets();
      res.status(200).json(response);
    })
  );

  router.post(
    '/add',
    asyncHandler(
      async (
        req: Request<{}, {}, AddWalletRequest>,
        res: Response<AddWalletResponse, {}>
      ) => {
        validateAddWalletRequest(req.body);
        res.status(200).json(await addWallet(req.body));
      }
    )
  );

  router.delete(
    '/remove',
    asyncHandler(
      async (
        req: Request<{}, {}, RemoveWalletRequest>,
        res: Response<void, {}>
      ) => {
        validateRemoveWalletRequest(req.body);
        await removeWallet(req.body);
        res.status(200).json();
      }
    )
  );
}
