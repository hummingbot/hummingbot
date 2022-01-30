import { Harmony } from './harmony';
import { NextFunction, Request, Response } from 'express';

export const verifyHarmonyIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const harmony = Harmony.getInstance();
  if (!harmony.ready()) {
    await harmony.init();
  }
  return next();
};
