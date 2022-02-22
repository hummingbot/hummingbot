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
  {
    title: 'Liquidity Mining',
    description:
      'This strategy allows market making across multiple pairs on an exchange on a single Hummingbot instance.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 2,
    placeType: 'gt',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Arbitrage',
    description:
      'This strategy monitor prices in two different trading pairs and executes offsetting buy and sell orders in both markets in order to capture arbitrage opportunities.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 3,
    placeType: 'gt',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Aroon Oscillator',
    description:
      'This strategy is a modified version of the Pure MM that uses the Aroon technical indicator to adjust order spreads based on the uptrend or downtrend signified by the indicator.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 4,
    placeType: 'lt',
    category: StrategyCategory.Binance,
  },
  {
    title: 'AMM Arbitrage',
    description:
      'This strategy monitors prices between a trading pair on an amm exchange versus another trading pair on another spot or amm exchange in order to identify arbitrage opportunities.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 7,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Avellaneda Market Making',
    description:
      'This strategy implements a market making strategy described in the classic paper High-frequency Trading in a Limit Order Book written by M. Avellaneda and S. Stoikov.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 6,
    placeType: 'lt',
    category: StrategyCategory.Binance,
  },
  {
    title: 'TWAP',
    description:
      'This strategy is a simple bot that places a series of limit orders on an exchange, while allowing users to control order size, price, and duration.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 5,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Celo Arbitrage',
    description:
      'This strategy is a predecessor to the amm_arb strategy built specifically to help Celo Protocol maintain price stability for its stablecoin pairs.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 8,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Cross-Exchange Market Making',
    description:
      'This strategy allows you to make a market (creates buy and sell orders) on the maker exchange, while hedging any filled trades on a second, taker exchange.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 9,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Hedge',
    description:
      'This strategy allows you to hedge a market making strategy by automatically opening short positions on dydx_perpetual or another perp exchange.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 10,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Perpetual Market Making',
    description:
      'This strategy allows Hummingbot users to run a market making strategy on a single trading pair on a perpetuals swap (perp) order book exchange.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 11,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Spot Perpetual Arbitrage',
    description:
      'This strategy looks at the price on the spot connector and the price on the derivative connector. Then it calculates the spread between the two connectors.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 13,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Uniswap-v3 LP ',
    description:
      'This strategy creates and maintains Uniswap positions as the market price changes in order to continue providing liquidity. Currently, it does not remove or update positions.',
    fileHref: '/',
    strategyName: StrategyName.PureMarketMaking,
    place: 12,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
];

export const $strategies = ref(strategies);
