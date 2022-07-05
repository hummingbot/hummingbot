import { Solana } from './solana';
import { NextFunction, Request, Response } from 'express';

export const verifySolanaIsAvailable = async (
  req: Request,
  _res: Response,
  next: NextFunction
) => {
  const solana = await Solana.getInstance(req.body.network);
  if (!solana.ready) {
    await solana.init();
  }

  return next();
};
