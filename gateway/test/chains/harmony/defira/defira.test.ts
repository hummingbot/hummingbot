jest.useFakeTimers();
const { MockProvider } = require('mock-ethers-provider');
import { FACTORY_ADDRESS } from '@zuzu-cat/defira-sdk';
import { Defira } from '../../../../src/connectors/defira/defira';
import { patch, unpatch } from '../../../services/patch';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import { Token, CurrencyAmount, TradeType, Percent } from '@uniswap/sdk-core';
import { Trade, Pair, Route } from '@zuzu-cat/defira-sdk';
import { BigNumber } from 'ethers';
import { Harmony } from '../../../../src/chains/harmony/harmony';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';
import { DefiraConfig } from '../../../../src/connectors/defira/defira.config';
import { abi as routerAbi } from '../../../../src/connectors/defira/defira_v2_router_abi.json';

let harmony: Harmony;
let defira: Defira;

const WONE = new Token(
  3,
  '0x1E120B3b4aF96e7F394ECAF84375b1C661830013',
  18,
  'WONE'
);
const ETH = new Token(
  3,
  '0x7466d7d0C21Fa05F32F5a0Fa27e12bdC06348Ce2',
  18,
  'ETH'
);

let mockProvider: typeof MockProvider;

beforeAll(async () => {
  harmony = Harmony.getInstance('testnet');
  patchEVMNonceManager(harmony.nonceManager);

  defira = Defira.getInstance('harmony', 'testnet');
  await defira.init();
});

beforeEach(() => {
  mockProvider = new MockProvider();
  patchEVMNonceManager(harmony.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await harmony.close();
});

const patchMockProvider = () => {
  mockProvider.setMockContract(
    DefiraConfig.config.routerAddress('testnet'),
    routerAbi
  );
  patch(defira, 'provider', () => {
    return mockProvider;
  });
};

const patchFetchData = () => {
  patch(defira, 'fetchPairData', () => {
    return new Pair(
      CurrencyAmount.fromRawAmount(WONE, '2000000000000000000'),
      CurrencyAmount.fromRawAmount(ETH, '1000000000000000000')
    );
  });
};

const patchTrade = (key: string, error?: Error) => {
  patch(Trade, key, () => {
    if (error) return [];
    const WONE_ETH = new Pair(
      CurrencyAmount.fromRawAmount(WONE, '2000000000000000000'),
      CurrencyAmount.fromRawAmount(ETH, '1000000000000000000')
    );
    const ETH_TO_WONE = new Route([WONE_ETH], ETH, WONE);
    return [
      new Trade(
        ETH_TO_WONE,
        CurrencyAmount.fromRawAmount(ETH, '1000000000000000'),
        TradeType.EXACT_INPUT
      ),
    ];
  });
};

describe('verify defira gasLimitEstimate', () => {
  it('Should initially match the config for mainnet', () => {
    expect(defira.gasLimitEstimate).toEqual(
      DefiraConfig.config.gasLimitEstimate()
    );
  });
});

describe('verify defira getAllowedSlippage', () => {
  it('Should parse simple fractions', () => {
    expect(defira.getAllowedSlippage('3/100')).toEqual(new Percent('3', '100'));
  });
});

describe('verify defira factory', () => {
  const expectedFactoryAddress = FACTORY_ADDRESS;
  beforeEach(() => {
    patchMockProvider();
    mockProvider.stub(
      DefiraConfig.config.routerAddress('testnet'),
      'factory',
      expectedFactoryAddress
    );
  });
  it('Returns the factory address via the provider', async () => {
    const factoryAddress = await defira.factory;
    expect(factoryAddress).toEqual(expectedFactoryAddress);
  });
});

describe('verify defira initCodeHash', () => {
  it('Should return the testnet factory initCodeHash', () => {
    expect(defira.initCodeHash).toEqual(
      DefiraConfig.config.initCodeHash('testnet')
    );
  });
});

describe('verify defira estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactIn');

    const expectedTrade = await defira.estimateSellTrade(
      WONE,
      ETH,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactIn', new Error('error getting trade'));

    await expect(async () => {
      await defira.estimateSellTrade(WONE, ETH, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify defira estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactOut');

    const expectedTrade = await defira.estimateBuyTrade(
      WONE,
      ETH,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactOut', new Error('error getting trade'));

    await expect(async () => {
      await defira.estimateBuyTrade(WONE, ETH, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify defira Token List', () => {
  it('Should return a token by address', async () => {
    const token = defira.getTokenByAddress(ETH.address);
    expect(token).toBeInstanceOf(Token);
  });
});
