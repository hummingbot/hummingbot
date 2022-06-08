import { Router } from 'express';
import { asyncHandler } from '../services/error-handler';
import { PangolinConfig } from './pangolin/pangolin.config';
import { PerpConfig } from './perp/perp.config';
import { TraderjoeConfig } from './traderjoe/traderjoe.config';
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
            name: 'perp',
            trading_type: PerpConfig.config.tradingTypes('perp'),
            available_networks: PerpConfig.config.availableNetworks,
          },
          {
            name: 'traderjoe',
            trading_type: TraderjoeConfig.config.tradingTypes,
            available_networks: TraderjoeConfig.config.availableNetworks,
          },
        ],
      });
    })
  );
}
