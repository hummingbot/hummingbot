import { ref } from 'vue';

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
  desc: string;
  place: number;
  placeType: 'equal' | 'lt' | 'gt';
  fileHref: string;
  startHref: string;
  category: StrategyCategory;
}

const strategies: Strategy[] = [
  {
    title: 'Pure Market Making',
    desc: 'This strategy allows Hummingbot users to run a market making strategy on a single trading pair on a spot exchanges.',
    fileHref: '/',
    startHref: '/',
    place: 1,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Liquidity Mining',
    desc: 'This strategy allows market making across multiple pairs on an exchange on a single Hummingbot instance.',
    fileHref: '/',
    startHref: '/',
    place: 2,
    placeType: 'gt',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Arbitrage',
    desc: 'This strategy monitor prices in two different trading pairs and executes offsetting buy and sell orders in both markets in order to capture arbitrage opportunities.',
    fileHref: '/',
    startHref: '/',
    place: 3,
    placeType: 'gt',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Aroon Oscillator',
    desc: 'This strategy is a modified version of the Pure MM that uses the Aroon technical indicator to adjust order spreads based on the uptrend or downtrend signified by the indicator.',
    fileHref: '/',
    startHref: '/',
    place: 4,
    placeType: 'lt',
    category: StrategyCategory.Binance,
  },
  {
    title: 'AMM Arbitrage',
    desc: 'This strategy monitors prices between a trading pair on an amm exchange versus another trading pair on another spot or amm exchange in order to identify arbitrage opportunities.',
    fileHref: '/',
    startHref: '/',
    place: 7,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Avellaneda Market Making',
    desc: 'This strategy implements a market making strategy described in the classic paper High-frequency Trading in a Limit Order Book written by M. Avellaneda and S. Stoikov.',
    fileHref: '/',
    startHref: '/',
    place: 6,
    placeType: 'lt',
    category: StrategyCategory.Binance,
  },
  {
    title: 'TWAP',
    desc: 'This strategy is a simple bot that places a series of limit orders on an exchange, while allowing users to control order size, price, and duration.',
    fileHref: '/',
    startHref: '/',
    place: 5,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Celo Arbitrage',
    desc: 'This strategy is a predecessor to the amm_arb strategy built specifically to help Celo Protocol maintain price stability for its stablecoin pairs.',
    fileHref: '/',
    startHref: '/',
    place: 8,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Cross-Exchange Market Making',
    desc: 'This strategy allows you to make a market (creates buy and sell orders) on the maker exchange, while hedging any filled trades on a second, taker exchange.',
    fileHref: '/',
    startHref: '/',
    place: 9,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Hedge',
    desc: 'This strategy allows you to hedge a market making strategy by automatically opening short positions on dydx_perpetual or another perp exchange.',
    fileHref: '/',
    startHref: '/',
    place: 10,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Perpetual Market Making',
    desc: 'This strategy allows Hummingbot users to run a market making strategy on a single trading pair on a perpetuals swap (perp) order book exchange.',
    fileHref: '/',
    startHref: '/',
    place: 11,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Spot Perpetual Arbitrage',
    desc: 'This strategy looks at the price on the spot connector and the price on the derivative connector. Then it calculates the spread between the two connectors.',
    fileHref: '/',
    startHref: '/',
    place: 13,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
  {
    title: 'Uniswap-v3 LP ',
    desc: 'This strategy creates and maintains Uniswap positions as the market price changes in order to continue providing liquidity. Currently, it does not remove or update positions.',
    fileHref: '/',
    startHref: '/',
    place: 12,
    placeType: 'equal',
    category: StrategyCategory.Binance,
  },
];

export const $strategies = ref(strategies);
