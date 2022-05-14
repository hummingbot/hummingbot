import { Router } from 'express';
import { asyncHandler } from '../services/error-handler';
import { DefiraConfig } from './defira/defira.config';
import { PangolinConfig } from './pangolin/pangolin.config';
import { UniswapConfig } from './uniswap/uniswap.config';

export namespace ConnectorsRoutes {
  export const router = Router();

  router.get(
    '/',
    asyncHandler(async (_req, res) => {
      res.status(200).json({
        connectors: [
          {
            name: 'uniswap',
            trading_type: UniswapConfig.config.tradingTypes('v2'),
            available_networks: UniswapConfig.config.availableNetworks,
          },
          {
            name: 'pangolin',
            trading_type: PangolinConfig.config.tradingTypes,
            available_networks: PangolinConfig.config.availableNetworks,
          },
          {
            name: 'defira',
            trading_type: DefiraConfig.config.tradingTypes,
            available_networks: DefiraConfig.config.availableNetworks,
          },
        ],
      });
    })
  );
}
