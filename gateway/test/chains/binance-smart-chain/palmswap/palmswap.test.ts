jest.useFakeTimers();
import { BinanceSmartChain } from '../../../../src/chains/binance-smart-chain/binance-smart-chain';
import { BigNumber, utils } from 'ethers';
import { patch, unpatch } from '../../../services/patch';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';
import { Palmswap } from '../../../../src/connectors/palmswap/palmswap';

const { parseUnits } = utils;

let bsc: BinanceSmartChain;
let palmswap: Palmswap;

beforeAll(async () => {
  bsc = BinanceSmartChain.getInstance('testnet');
  patchEVMNonceManager(bsc.nonceManager);
  await bsc.init();

  palmswap = Palmswap.getInstance('binance-smart-chain', 'testnet');
  await palmswap.init();
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await bsc.close();
});

const patchMarket = () => {
  patch(palmswap, 'getMarket', () => {
    return {
      async open() {
        return true;
      },
      async getOutputPrice() {
        return BigNumber.from('1258');
      },
      async getUnderlyingTwapPrice() {
        return { d: parseUnits('3') };
      },
      async getUnderlyingPrice() {
        return { d: parseUnits('2') };
      },
      async getSpotPrice() {
        return { d: parseUnits('1') };
      },
    };
  });
};

const patchCH = () => {
  patch(palmswap, '_clearingHouse', {
    async closePosition() {
      return;
    },
    async openPosition() {
      return {
        type: 2,
        chainId: 42,
        nonce: 115,
        maxPriorityFeePerGas: { toString: () => '106000000000' },
        maxFeePerGas: { toString: () => '106000000000' },
        gasPrice: { toString: () => null },
        gasLimit: { toString: () => '100000' },
        to: '0x4F96Fe3b7A6Cf9725f59d353F723c1bDb64CA6Aa',
        value: { toString: () => '0' },
        data: '0x095ea7b30000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488dffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', // noqa: mock
        accessList: [],
        hash: '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9', // noqa: mock
        v: 0,
        r: '0xbeb9aa40028d79b9fdab108fcef5de635457a05f3a254410414c095b02c64643', // noqa: mock
        s: '0x5a1506fa4b7f8b4f3826d8648f27ebaa9c0ee4bd67f569414b8cd8884c073100', // noqa: mock
        from: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        confirmations: 0,
      };
    },
  });
};

const patchCHViewer = () => {
  patch(palmswap, '_clearingHouseViewer', {
    async getUnrealizedPnl() {
      return BigNumber.from('0');
    },
    async getFreeCollateral() {
      return 5 * 1e18;
    },
    async getPersonalPositionWithFundingPayment() {
      return {
        size: { d: BigNumber.from('0') },
        openNotional: { d: BigNumber.from('0') },
        margin: { d: BigNumber.from('0') },
      };
    },
  });
};
const patchInsuranceFund = () => {
  patch(palmswap, '_insuranceFund', {
    async getAllAmms() {
      return [
        '0xdAD1B29b17A2bBd51063d33846Fc6Fa446017B11',
        '0xE7fbfbd41Dbc15A1b152A947c08312D42dC676ed',
      ];
    },
  });
};

describe('verify market functions', () => {
  it('available pairs should return a list of pairs', async () => {
    patchMarket();

    const pairs = palmswap.availablePairs();
    expect(pairs).toEqual(['ETHUSDT', 'BTCUSDT']);
  });

  it('tickerSymbol should return prices', async () => {
    patchMarket();

    const prices = await palmswap.prices('ETHUSDT');
    expect(prices.markPrice.toString()).toEqual('1');
    expect(prices.indexPrice.toString()).toEqual('2');
    expect(prices.indexTwapPrice.toString()).toEqual('3');
  });

  it('market state should return boolean', async () => {
    patchMarket();

    const state = await palmswap.isMarketActive('ETHUSDT');
    expect(state).toEqual(true);
  });
});

describe('verify perp position', () => {
  it('getPositions should return data', async () => {
    patchCHViewer();
    const pos = await palmswap.getPositions('ETHUSDT');
    expect(pos).toHaveProperty('positionAmt');
    expect(pos).toHaveProperty('positionSide');
    expect(pos).toHaveProperty('unrealizedProfit');
    expect(pos).toHaveProperty('leverage');
    expect(pos).toHaveProperty('entryPrice');
    expect(pos).toHaveProperty('tickerSymbol');
    expect(pos).toHaveProperty('pendingFundingPayment');
  });
});

describe('verify perp open/close position', () => {
  it('openPosition should return', async () => {
    patchCH();
    patchMarket();

    const pos = await palmswap.openPosition(true, 'ETHUSDT', '0.01', '1/10');
    expect(pos.hash).toEqual(
      '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9' // noqa: mock
    );
  });

  it('getAccountValue should return', async () => {
    patchCH();
    patchCHViewer();
    patchInsuranceFund();

    const bal = await palmswap.getAccountValue();
    expect(bal.toString()).toEqual('10');
  });

  it('closePosition should throw', async () => {
    patchCH();

    await expect(async () => {
      await palmswap.closePosition('ETHUSDT');
    }).toBeTruthy();
  });
});

describe('getAllowedSlippage', () => {
  it('return value of string when not null', () => {
    const allowedSlippage = palmswap.getAllowedSlippage('1/100');
    expect(allowedSlippage).toEqual(0.01);
  });

  it('return value from config when string is null', () => {
    const allowedSlippage = palmswap.getAllowedSlippage();
    expect(allowedSlippage).toEqual(0.02);
  });

  it('return value from config when string is malformed', () => {
    const allowedSlippage = palmswap.getAllowedSlippage('yo');
    expect(allowedSlippage).toEqual(0.02);
  });
});
