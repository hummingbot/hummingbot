import { NextFunction, Request, Response } from 'express';
import { XRPLDEX } from './xrpldex';
import { HttpException } from '../../services/error-handler';

export const verifyXRPLDEXIsAvailable = async (
  req: Request,
  _res: Response,
  next: NextFunction
) => {
  if (!req || !req.body || !req.body.network) {
    throw new HttpException(404, 'No XRPL network informed.');
  }

  const xrplDEX = XRPLDEX.getInstance(req.body.chain, req.body.network);

  if (!xrplDEX.isConnected()) {
    await xrplDEX.client.connect();
  }

  return next();
};
