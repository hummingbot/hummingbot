import { Router } from 'express';
import { asyncHandler } from '../services/error-handler';
import { PangolinConfig } from './pangolin/pangolin.config';
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
            trading_type: UniswapConfig.config.tradingTypes('swap'),
            available_networks: UniswapConfig.config.availableNetworks,
          },
          {
            name: 'uniswapLP',
            trading_type: UniswapConfig.config.tradingTypes('LP'),
            available_networks: UniswapConfig.config.availableNetworks,
            additional_spenders: ['uniswap'],
          },
          {
            name: 'pangolin',
            trading_type: PangolinConfig.config.tradingTypes,
            available_networks: PangolinConfig.config.availableNetworks,
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
