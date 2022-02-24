import { ref } from 'vue';

export enum StrategyName {
  PureMarketMaking = 'pure-market-making',
}

export enum StrategyCategory {
  All = 'All exchanges',
  Binance = 'Binance',
  AscendEX = 'AscendEX',
  CryptoCom = 'Crypto.com',
  Kucoin = 'Kucoin',
  BinanceUS = 'BinanceUS',
}

interface Strategy {
  title: string;
  description: string;
  place: number;
  placeType: 'equal' | 'lt' | 'gt';
  fileHref: string;
  strategyName: StrategyName;
  category: StrategyCategory;
}

const strategies: Strategy[] = [
  {
    title: 'Pure Market Making',
    description:
      'This strategy allows Hummingbot users to run a market making strategy on a single trading pair on a spot exchanges.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 1,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
];

export const $strategies = ref(strategies);
