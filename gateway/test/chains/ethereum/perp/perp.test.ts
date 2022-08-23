jest.useFakeTimers();
import { Perp } from '../../../../src/connectors/perp/perp';
import { MarketStatus } from '@perp/sdk-curie';
import { patch, unpatch } from '../../../services/patch';
import { Big } from 'big.js';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';

let ethereum: Ethereum;
let perp: Perp;

beforeAll(async () => {
  ethereum = Ethereum.getInstance('optimism');
  patchEVMNonceManager(ethereum.nonceManager);
  await ethereum.init();

  perp = Perp.getInstance('ethereum', 'optimism');
});

beforeEach(() => {
  patchEVMNonceManager(ethereum.nonceManager);
});

afterEach(() => {
  unpatch();
});

const patchMarket = () => {
  patch(perp.perp, 'markets', () => {
    return {
      getMarket() {
        return {
          getPrices() {
            return {
              markPrice: new Big('1'),
              indexPrice: new Big('2'),
              indexTwapPrice: new Big('3'),
            };
          },
          async getStatus() {
            return MarketStatus.ACTIVE;
          },
        };
      },
      get marketMap() {
        return {
          AAVEUSD: 1,
          WETHUSD: 2,
          WBTCUSD: 3,
        };
      },
    };
  });
};

const patchPosition = () => {
  patch(perp.perp, 'positions', () => {
    return {
      getTakerPositionByTickerSymbol() {
        return;
      },
      getTotalPendingFundingPayments() {
        return {};
      },
    };
  });
};

const patchCH = () => {
  patch(perp.perp, 'clearingHouse', () => {
    return {
      createPositionDraft() {
        return;
      },
      async openPosition() {
        return {
          transaction: {
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
          },
        };
      },
      async getAccountValue() {
        return new Big('10');
      },
    };
  });
};

describe('verify market functions', () => {
  it('available pairs should return a list of pairs', async () => {
    patchMarket();

    const pairs = perp.availablePairs();
    expect(pairs).toEqual(['AAVEUSD', 'WETHUSD', 'WBTCUSD']);
  });

  it('tickerSymbol should return prices', async () => {
    patchMarket();

    const prices = await perp.prices('AAVEUSD');
    expect(prices.markPrice.toString()).toEqual('1');
    expect(prices.indexPrice.toString()).toEqual('2');
    expect(prices.indexTwapPrice.toString()).toEqual('3');
  });

  it('market state should return boolean', async () => {
    patchMarket();

    const state = await perp.isMarketActive('AAVEUSD');
    expect(state).toEqual(true);
  });
});

describe('verify perp position', () => {
  it('getPositions should return data', async () => {
    patchPosition();

    const pos = await perp.getPositions('AAVEUSD');
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

    const pos = await perp.openPosition(true, 'AAVEUSD', '0.01', '1/10');
    expect(pos.hash).toEqual(
      '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9' // noqa: mock
    );
  });

  it('getAccountValue should return', async () => {
    patchCH();

    const bal = await perp.getAccountValue();
    expect(bal.toString()).toEqual('10');
  });

  it('closePosition should throw', async () => {
    patchPosition();
    patchCH();

    await expect(async () => {
      await perp.closePosition('AAVEUSD', '1/10');
    }).rejects.toThrow(new Error(`No active position on AAVEUSD.`));
  });
});

describe('getAllowedSlippage', () => {
  it('return value of string when not null', () => {
    const allowedSlippage = perp.getAllowedSlippage('1/100');
    expect(allowedSlippage).toEqual(0.01);
  });

  it('return value from config when string is null', () => {
    const allowedSlippage = perp.getAllowedSlippage();
    expect(allowedSlippage).toEqual(0.02);
  });

  it('return value from config when string is malformed', () => {
    const allowedSlippage = perp.getAllowedSlippage('yo');
    expect(allowedSlippage).toEqual(0.02);
  });
});
