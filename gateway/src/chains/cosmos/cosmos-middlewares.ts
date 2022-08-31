import { Cosmos } from './cosmos';
import { NextFunction, Request, Response } from 'express';
import { CosmosConfig } from './cosmos.config';

export const verifyCosmosIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const cosmos = Cosmos.getInstance(CosmosConfig.config.network.name);
  if (!cosmos.ready()) {
    await cosmos.init();
  }
  return next();
};
