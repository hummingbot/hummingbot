import { Router } from 'express';
import { asyncHandler } from '../services/error-handler';
import { DefiraConfig } from './defira/defira.config';
import { DefikingdomsConfig } from './defikingdoms/defikingdoms.config';
import { MadMeerkatConfig } from './mad_meerkat/mad_meerkat.config';
import { OpenoceanConfig } from './openocean/openocean.config';
import { PangolinConfig } from './pangolin/pangolin.config';
import { PerpConfig } from './perp/perp.config';
import { QuickswapConfig } from './quickswap/quickswap.config';
import { SerumConfig } from './serum/serum.config';
import { SushiswapConfig } from './sushiswap/sushiswap.config';
import { TraderjoeConfig } from './traderjoe/traderjoe.config';
import { UniswapConfig } from './uniswap/uniswap.config';
import { VVSConfig } from './vvs/vvs.config';
import { RefConfig } from './ref/ref.config';
import { PancakeSwapConfig } from './pancakeswap/pancakeswap.config';

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
            available_networks: JSON.parse(
              JSON.stringify(UniswapConfig.config.availableNetworks)
            ),
            additional_spenders: ['uniswap'],
          },
          {
            name: 'pangolin',
            trading_type: PangolinConfig.config.tradingTypes,
            available_networks: PangolinConfig.config.availableNetworks,
          },
          {
            name: 'openocean',
            trading_type: OpenoceanConfig.config.tradingTypes,
            available_networks: OpenoceanConfig.config.availableNetworks,
          },
          {
            name: 'quickswap',
            trading_type: QuickswapConfig.config.tradingTypes,
            available_networks: QuickswapConfig.config.availableNetworks,
          },
          {
            name: 'perp',
            trading_type: PerpConfig.config.tradingTypes('perp'),
            available_networks: PerpConfig.config.availableNetworks,
          },
          {
            name: 'sushiswap',
            trading_type: SushiswapConfig.config.tradingTypes,
            available_networks: SushiswapConfig.config.availableNetworks,
          },
          {
            name: 'traderjoe',
            trading_type: TraderjoeConfig.config.tradingTypes,
            available_networks: TraderjoeConfig.config.availableNetworks,
          },
          {
            name: 'defikingdoms',
            trading_type: DefikingdomsConfig.config.tradingTypes,
            available_networks: DefikingdomsConfig.config.availableNetworks,
          },
          {
            name: 'defira',
            trading_type: DefiraConfig.config.tradingTypes,
            available_networks: DefiraConfig.config.availableNetworks,
          },
          {
            name: 'serum',
            trading_type: SerumConfig.config.tradingTypes,
            available_networks: SerumConfig.config.availableNetworks,
          },
          {
            name: 'mad_meerkat',
            trading_type: MadMeerkatConfig.config.tradingTypes,
            available_networks: MadMeerkatConfig.config.availableNetworks,
          },
          {
            name: 'vvs',
            trading_type: VVSConfig.config.tradingTypes,
            available_networks: VVSConfig.config.availableNetworks,
          },
          {
            name: 'ref',
            trading_type: RefConfig.config.tradingTypes,
            available_networks: RefConfig.config.availableNetworks,
          },
          {
            name: 'pancakeswap',
            trading_type: PancakeSwapConfig.config.tradingTypes,
            available_networks: PancakeSwapConfig.config.availableNetworks,
          },
        ],
      });
    })
  );
}
