jest.useFakeTimers();
import { Curve } from '../../../src/connectors/curve/curve';
import { TokenInfo } from '../../../src/services/ethereum-base';
import { patch, unpatch } from '../../services/patch';
import { Ethereum } from '../../../src/chains/ethereum/ethereum';
import { patchEVMNonceManager } from '../../evm.nonce.mock';
import { default as curve_ } from '@curvefi/api';

let ethereum: Ethereum;
let curve: Curve;

const WETH: TokenInfo = {
  chainId: 1,
  address: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
  name: 'WETH',
  symbol: 'WETH',
  decimals: 18,
};

const DAI: TokenInfo = {
  chainId: 1,
  address: '0x6B175474E89094C44Da98b954EedeAC495271d0F',
  name: 'DAI',
  symbol: 'DAI',
  decimals: 18,
};

const patchCurveInit = () => {
  patch(curve_, 'init', () => {
    return null;
  });
};

beforeAll(async () => {
  ethereum = Ethereum.getInstance('mainnet');
  patchEVMNonceManager(ethereum.nonceManager);
  await ethereum.init();

  patchCurveInit();
  curve = Curve.getInstance('ethereum', 'mainnet');
  await curve.init();
});

beforeEach(() => {
  patchEVMNonceManager(ethereum.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await ethereum.close();
});

const patchGetBestRouteAndOutput = () => {
  patch(curve_.router, 'getBestRouteAndOutput', () => {
    return { route: null, output: '10000000' };
  });
};

const patchRouterExchangeExpected = () => {
  patch(curve_.router, 'routerExchangeExpected', () => {
    return '10000000';
  });
};

// const patchTrade = (key: string, error?: Error) => {
//   patch(Trade, key, () => {
//     if (error) return [];
//     const DAI_WETH = new Pair(
//       new TokenAmount(DAI, '2000000000000000000'),
//       new TokenAmount(WETH, '1000000000000000000'),
//       43114
//     );
//     const WETH_TO_DAI = new Route([DAI_WETH], WETH);
//     return [
//       new Trade(
//         WETH_TO_DAI,
//         new TokenAmount(WETH, '1000000000000000'),
//         TradeType.EXACT_INPUT,
//         43114
//       ),
//     ];
//   });
// };

describe('verify Curve estimateTrade', () => {
  it('Should return an ExpectedTrade when selling', async () => {
    patchGetBestRouteAndOutput();
    patchRouterExchangeExpected();

    const expectedTrade = await curve.estimateTrade(DAI, WETH, '1', 'SELL');
    expect(expectedTrade).toHaveProperty('route');
    expect(expectedTrade).toHaveProperty('outputAmount');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an ExpectedTrade when buying', async () => {
    patchGetBestRouteAndOutput();
    patchRouterExchangeExpected();

    const expectedTrade = await curve.estimateTrade(DAI, WETH, '1', 'BUY');
    expect(expectedTrade).toHaveProperty('route');
    expect(expectedTrade).toHaveProperty('outputAmount');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });
});

describe('getAllowedSlippage', () => {
  it('return value of string when not null', () => {
    const allowedSlippage = curve.getAllowedSlippage('3/100');
    expect(allowedSlippage).toEqual(3 / 100);
  });

  it('return value from config when string is null', () => {
    const allowedSlippage = curve.getAllowedSlippage();
    expect(allowedSlippage).toEqual(1 / 100);
  });

  it('return value from config when string is malformed', () => {
    const allowedSlippage = curve.getAllowedSlippage('yo');
    expect(allowedSlippage).toEqual(1 / 100);
  });
});
