/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { Router, Request, Response } from 'express';
import { asyncHandler } from '../error-handler';
import { ConfigUpdateRequest } from './config.requests';
import {
  validateConfigUpdateRequest,
  updateAllowedSlippageToFraction,
} from './config.validators';
import { ConfigManagerV2 } from '../config-manager-v2';

export namespace ConfigRoutes {
  export const router = Router();

  router.post(
    '/update',
    asyncHandler(
      async (
        req: Request<unknown, unknown, ConfigUpdateRequest>,
        res: Response
      ) => {
        validateConfigUpdateRequest(req.body);
        const config = ConfigManagerV2.getInstance().get(req.body.configPath);
        if (typeof req.body.configValue == 'string')
          switch (typeof config) {
            case 'number':
              req.body.configValue = Number(req.body.configValue);
              break;
            case 'boolean':
              req.body.configValue =
                req.body.configValue.toLowerCase() === 'true';
              break;
          }

        if (req.body.configPath.endsWith('allowedSlippage')) {
          updateAllowedSlippageToFraction(req.body);
        }

        ConfigManagerV2.getInstance().set(
          req.body.configPath,
          req.body.configValue
        );

        res.status(200).json({ message: 'The config has been updated' });
      }
    )
  );
}
