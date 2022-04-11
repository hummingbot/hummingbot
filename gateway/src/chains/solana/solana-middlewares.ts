import { Solana } from './solana';
import { NextFunction, Request, Response } from 'express';

export const verifySolanaIsAvailable = async (
  req: Request,
  _res: Response,
  next: NextFunction
) => {
  const solana = Solana.getInstance(req.body.chain);
  if (!solana.ready()) {
    await solana.init();
  }

  return next();
};
