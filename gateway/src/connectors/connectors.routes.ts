import { Router, Response } from 'express';
import { asyncHandler } from '../services/error-handler';

export namespace ConnectorsRoutes {
  export const router = Router();

  router.get(
    '/',
    asyncHandler(async (_req, res: Response<any, {}>) => {
      res.status(200).json({
        connectors: [{}]
      });
    })
  );
}
