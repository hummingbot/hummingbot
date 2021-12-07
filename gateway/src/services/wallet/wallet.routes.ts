/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { Avalanche } from '../../chains/avalanche/avalanche';

import { asyncHandler } from '../error-handler';
import { verifyEthereumIsAvailable } from '../../chains/ethereum/ethereum-middlewares';

import { addWallet, removeWallet, getWallets } from './wallet.controllers';

import {
  AddWalletRequest,
  RemoveWalletRequest,
  GetWalletResponse,
} from './wallet.requests';

export namespace WalletRoutes {
  export const router = Router();
  export const ethereum = Ethereum.getInstance();
  export const avalanche = Avalanche.getInstance();

  router.use(asyncHandler(verifyEthereumIsAvailable));

  router.post(
    '/wallet/add',
    asyncHandler(
      async (
        req: Request<{}, {}, AddWalletRequest>,
        res: Response<void, {}>
      ) => {
        addWallet(ethereum, avalanche, req.body);
        res.status(200);
      }
    )
  );

  router.post(
    '/wallet/remove',
    asyncHandler(
      async (
        req: Request<{}, {}, RemoveWalletRequest>,
        res: Response<void, {}>
      ) => {
        removeWallet(req.body);
        res.status(200);
      }
    )
  );

  router.get(
    '/wallets',
    asyncHandler(async (_req, res: Response<GetWalletResponse[], {}>) => {
      const response = await getWallets();
      res.status(200).json(response);
    })
  );
}
