import { HttpException } from '../../services/error-handler';
import { Ripple } from './ripple';
import { NextFunction, Request, Response } from 'express';

export const verifySolanaIsAvailable = async (
  req: Request,
  _res: Response,
  next: NextFunction
) => {
  if (!req || !req.body || !req.body.network) {
    throw new HttpException(404, 'No Ripple network informed.');
  }

  const solana = await Ripple.getInstance(req.body.network);
  if (!solana.ready) {
    await solana.init();
  }

  return next();
};
