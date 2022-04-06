import { NextFunction, Request, Response } from 'express';
import { Serum } from './serum';

export const verifySerumIsAvailable = async (
  req: Request,
  _res: Response,
  next: NextFunction
) => {
  await Serum.getInstance(req.body.chain, req.body.network);

  return next();
};
