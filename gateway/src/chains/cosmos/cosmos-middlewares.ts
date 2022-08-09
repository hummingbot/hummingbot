/* WIP */
import { Cosmos } from './cosmos';
import { NextFunction, Request, Response } from 'express';

export const verifyCosmosIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const cosmos = Cosmos.getInstance('mainnet');
  if (!cosmos.ready()) {
    await cosmos.init();
  }
  return next();
};
