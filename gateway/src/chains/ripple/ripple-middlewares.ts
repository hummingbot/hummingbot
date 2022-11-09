import { HttpException } from '../../services/error-handler';
import { Ripple } from './ripple';
import { NextFunction, Request, Response } from 'express';

export const verifyRippleIsAvailable = async (
  req: Request,
  _res: Response,
  next: NextFunction
) => {
  if (!req || !req.body || !req.body.network) {
    throw new HttpException(404, 'No Ripple network informed.');
  }

  const ripple = await Ripple.getInstance(req.body.network);
  if (!ripple.ready) {
    await ripple.init();
  }

  return next();
};
