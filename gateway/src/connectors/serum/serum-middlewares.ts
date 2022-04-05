import { NextFunction, Request, Response } from 'express';
import { Serum } from './serum';

export const verifySerumIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const serum = Serum.getInstance();
  if (!serum.ready) {
    await serum.init();
  }
  return next();
};
