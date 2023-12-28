import { Request, RequestHandler, Response, NextFunction } from 'express';

// Capture errors from an async route, this must wrap any route that uses async.
// For example, `app.get('/', asyncHandler(async (req, res) -> {...}))`
export const asyncHandler = (fn: RequestHandler) => (req: Request, res: Response, next: NextFunction) => {
  return Promise.resolve(fn(req, res, next)).catch(next);
};
