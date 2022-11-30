import { NextFunction, Request, Response } from 'express';
import { RippleDEX } from './rippledex';
import { HttpException } from '../../services/error-handler';

export const verifyRippleDEXIsAvailable = async (
  req: Request,
  _res: Response,
  next: NextFunction
) => {
  if (!req || !req.body || !req.body.network) {
    throw new HttpException(404, 'No Ripple network informed.');
  }

  const rippleDEX = RippleDEX.getInstance(req.body.chain, req.body.network);

  if (!rippleDEX.isConnected()) {
    await rippleDEX.client.connect();
  }

  return next();
};
