import { NextFunction, Request, Response } from 'express';
import { RippleDEX } from './rippledex';

export const verifyRippleDEXIsAvailable = async (
  request: Request,
  _response: Response,
  next: NextFunction
) => {
  await RippleDEX.getInstance(request.body.chain, request.body.network);

  return next();
};
