import { Ethereum } from './ethereum';
import { NextFunction, Request, Response } from 'express';

export const verifyEthereumIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const ethereum = Ethereum.getInstance();
  console.log('corro el middleware', ethereum.ready());
  if (!ethereum.ready()) {
    await ethereum.init();
  }
  console.log('corro el middleware abajo', ethereum.ready());
  return next();
};
