import { Solana } from './solana';
import { NextFunction, Request, Response } from 'express';

export const verifySolanaIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const solana = Solana.getInstance();
  if (!solana.ready()) {
    await solana.init();
  }
  return next();
};
