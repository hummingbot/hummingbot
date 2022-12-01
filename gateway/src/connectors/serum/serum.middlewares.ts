import { NextFunction, Request, Response } from 'express';
import { Serum } from './serum';

export const verifySerumIsAvailable = async (
  request: Request,
  _response: Response,
  next: NextFunction
) => {
  await Serum.getInstance(request.body.chain, request.body.network);

  return next();
};
