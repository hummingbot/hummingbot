import { HttpException } from '../../services/error-handler';
import { Solana } from './solana';
import { NextFunction, Request, Response } from 'express';

export const verifySolanaIsAvailable = async (
  req: Request,
  _res: Response,
  next: NextFunction
) => {
  if (!req || !req.body || !req.body.network) {
    throw new HttpException(404, 'No Solana network informed.');
  }

  const solana = await Solana.getInstance(req.body.network);
  if (!solana.ready) {
    await solana.init();
  }

  return next();
};
