import { HttpException } from '../../services/error-handler';
import { XRPL } from './xrpl';
import { NextFunction, Request, Response } from 'express';

export const verifyXRPLIsAvailable = async (
  req: Request,
  _res: Response,
  next: NextFunction
) => {
  if (!req || !req.body || !req.body.network) {
    throw new HttpException(404, 'No XRPL network informed.');
  }

  const xrpl = await XRPL.getInstance(req.body.network);
  if (!xrpl.ready) {
    await xrpl.init();
  }

  if (!xrpl.isConnected()) {
    await xrpl.client.connect();
  }

  return next();
};
