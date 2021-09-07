import { Ethereum } from './ethereum';
import { NextFunction, Request, Response } from 'express';

export const verifyEthereumIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const ethereum = Ethereum.getInstance();
  if (!ethereum.ready()) {
    await ethereum.init();
  }
  return next();
};
