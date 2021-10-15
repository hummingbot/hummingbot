import { Request, RequestHandler, Response, NextFunction } from 'express';

// custom error for http exceptions
export class HttpException extends Error {
  status: number;
  errorMessage: string;
  constructor(status: number, errorMessage: string) {
    super(errorMessage);
    this.status = status;
    this.errorMessage = errorMessage;
  }
}

export class GatewayError extends Error {
  errorMessage: string;
  errorCode: number;
  httpErrorCode: number;
  constructor(httpErrorCode: number, errorCode: number, errorMessage: string) {
    super(errorMessage);
    this.httpErrorCode = httpErrorCode;
    this.errorCode = errorCode;
    this.errorMessage = errorMessage;
  }
}

// Capture errors from an async route, this must wrap any route that uses async.
// For example, `app.get('/', asyncHandler(async (req, res) -> {...}))`
export const asyncHandler =
  (fn: RequestHandler) => (req: Request, res: Response, next: NextFunction) => {
    return Promise.resolve(fn(req, res, next)).catch(next);
  };
