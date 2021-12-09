import { Mango } from './mango';
import { NextFunction, Request, Response } from 'express';

export const verifyMangoIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const mango = Mango.getInstance();
  if (!mango.ready()) {
    await mango.init();
  }
  return next();
};
