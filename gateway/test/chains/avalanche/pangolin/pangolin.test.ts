jest.useFakeTimers();
import { Pangolin } from '../../../../src/connectors/pangolin/pangolin';
import { patch, unpatch } from '../../../services/patch';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import {
  Fetcher,
  Pair,
  Percent,
  Route,
  // Router,
  Token,
  TokenAmount,
  Trade,
  TradeType,
} from '@pangolindex/sdk';
import { BigNumber } from 'ethers';
// import { BigNumber, Contract, Wallet } from 'ethers';
import { Avalanche } from '../../../../src/chains/avalanche/avalanche';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';
let avalanche: Avalanche;
let pangolin: Pangolin;

// let wallet: Wallet;

const WETH = new Token(
  43114,
  '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
  18,
  'WETH'
);
const WAVAX = new Token(
  43114,
  '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
  18,
  'WAVAX'
);

// const TX = {
//   type: 2,
//   chainId: 42,
//   nonce: 115,
//   maxPriorityFeePerGas: { toString: () => '106000000000' },
//   maxFeePerGas: { toString: () => '106000000000' },
//   gasPrice: { toString: () => null },
//   gasLimit: { toString: () => '100000' },
//   to: '0x4F96Fe3b7A6Cf9725f59d353F723c1bDb64CA6Aa',
//   value: { toString: () => '0' },
//   data: '0x095ea7b30000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488dffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', // noqa: mock
//   accessList: [],
//   hash: '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9', // noqa: mock
//   v: 0,
//   r: '0xbeb9aa40028d79b9fdab108fcef5de635457a05f3a254410414c095b02c64643', // noqa: mock
//   s: '0x5a1506fa4b7f8b4f3826d8648f27ebaa9c0ee4bd67f569414b8cd8884c073100', // noqa: mock
//   from: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
//   confirmations: 0,
// };

beforeAll(async () => {
  avalanche = Avalanche.getInstance('fuji');
  patchEVMNonceManager(avalanche.nonceManager);
  await avalanche.init();
  // wallet = new Wallet(
  //   '0000000000000000000000000000000000000000000000000000000000000002', // noqa: mock
  //   avalanche.provider
  // );

  pangolin = Pangolin.getInstance('avalanche', 'fuji');
  await pangolin.init();
});

beforeEach(() => {
  patchEVMNonceManager(avalanche.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await avalanche.close();
});

const patchFetchPairData = () => {
  patch(Fetcher, 'fetchPairData', () => {
    return new Pair(
      new TokenAmount(WETH, '2000000000000000000'),
      new TokenAmount(WAVAX, '1000000000000000000'),
      43114
    );
  });
};

const patchTrade = (key: string, error?: Error) => {
  patch(Trade, key, () => {
    if (error) return [];
    const WETH_WAVAX = new Pair(
      new TokenAmount(WETH, '2000000000000000000'),
      new TokenAmount(WAVAX, '1000000000000000000'),
      43114
    );
    const WAVAX_TO_WETH = new Route([WETH_WAVAX], WAVAX);
    return [
      new Trade(
        WAVAX_TO_WETH,
        new TokenAmount(WAVAX, '1000000000000000'),
        TradeType.EXACT_INPUT,
        43114
      ),
    ];
  });
};

// const patchSwapCallParameters = () => {
//   patch(Router, 'swapCallParameters', () => {
//     return {
//       methodName: 'testMethodName',
//       args: {
//         testArgs: 'testValue',
//       },
//       value: '111111111',
//     };
//   });
// };

// const patchGetAllowedSlippage = () => {
//   patch(pangolin, 'getAllowedSlippage', () => {
//     return new Percent('1', '100');
//   });
// };

// const patchGetNextNonce = () => {
//   patch(avalanche.nonceManager, 'getNextNonce', async () => {
//     return 1;
//   });
// };

// const patchContractExecution = async () => {
//   patch(Contract, 'swapExactTokensForTokens', async () => {
//     return TX;
//   });
// };

// const patchCommitNonce = async () => {
//   patch(avalanche.nonceManager, 'commitNonce', async () => {
//     return null;
//   });
// };

describe('verify Pangolin estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn');

    const expectedTrade = await pangolin.estimateSellTrade(
      WETH,
      WAVAX,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn', new Error('error getting trade'));

    await expect(async () => {
      await pangolin.estimateSellTrade(WETH, WAVAX, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Pangolin estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut');

    const expectedTrade = await pangolin.estimateBuyTrade(
      WETH,
      WAVAX,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut', new Error('error getting trade'));

    await expect(async () => {
      await pangolin.estimateBuyTrade(WETH, WAVAX, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('getAllowedSlippage', () => {
  it('return value of string when not null', () => {
    const allowedSlippage = pangolin.getAllowedSlippage('3/100');
    expect(allowedSlippage).toEqual(new Percent('3', '100'));
  });

  it('return value from config when string is null', () => {
    const allowedSlippage = pangolin.getAllowedSlippage();
    expect(allowedSlippage).toEqual(new Percent('1', '100'));
  });

  it('return value from config when string is malformed', () => {
    const allowedSlippage = pangolin.getAllowedSlippage('yo');
    expect(allowedSlippage).toEqual(new Percent('1', '100'));
  });
});

// describe('executeTrade', () => {
//   it('test avalanche.nonceManager, successful execution returns transaction details', async () => {
//     patchSwapCallParameters();
//     patchGetAllowedSlippage();
//     patchGetNextNonce();
//     patchContractExecution();
//     patchCommitNonce();

//     const WETH_WAVAX = new Pair(
//       new TokenAmount(WETH, '2000000000000000000'),
//       new TokenAmount(WAVAX, '1000000000000000000'),
//       43114
//     );
//     const WAVAX_TO_WETH = new Route([WETH_WAVAX], WAVAX);
//     const TRADE = new Trade(
//       WAVAX_TO_WETH,
//       new TokenAmount(WAVAX, '1000000000000000'),
//       TradeType.EXACT_INPUT,
//       43114
//     );
//     const result = await pangolin.executeTrade(
//       wallet,
//       TRADE,
//       1,
//       pangolin.router,
//       pangolin.ttl,
//       pangolin.routerAbi,
//       pangolin.gasLimitEstimate
//     );
//     console.log(JSON.stringify(result));
//   });
// });
