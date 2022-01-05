import { Ethereum } from './ethereum';
import { NextFunction, Request, Response } from 'express';
import { NewEthereum } from './new_ethereum';

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

export const verifyNewEthereumIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const ethereum = NewEthereum.getInstance(_req.body.network);
  if (!ethereum.ready()) {
    await ethereum.init();
  }
  return next();
};
