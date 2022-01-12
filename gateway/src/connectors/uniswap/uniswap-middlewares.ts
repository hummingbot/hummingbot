import { Uniswap } from './uniswap';
import { NextFunction, Request, Response } from 'express';
import { NewUniswap } from './new_uniswap';

export const verifyUniswapIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const uniswap = Uniswap.getInstance();
  if (!uniswap.ready()) {
    await uniswap.init();
  }
  return next();
};

export const verifyNewUniswapIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const uniswap = NewUniswap.getInstance(_req.body.chain, _req.body.network);
  if (!uniswap.ready()) {
    await uniswap.init();
  }
  return next();
};
