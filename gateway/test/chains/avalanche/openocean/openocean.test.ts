import { patchEVMNonceManager } from '../../../evm.nonce.mock';

jest.useFakeTimers();
jest.setTimeout(30000);
import { Openocean } from '../../../../src/connectors/openocean/openocean';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import { Token } from '@uniswap/sdk';
import { BigNumber } from 'ethers';
import { Avalanche } from '../../../../src/chains/avalanche/avalanche';

let avalanche: Avalanche;
let openocean: Openocean;

const USDC = new Token(
  43114,
  '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
  6,
  'USDC'
);
const WAVAX = new Token(
  43114,
  '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
  18,
  'WAVAX'
);
const bDAI = new Token(
  43114,
  '0x6807eD4369d9399847F306D7d835538915fA749d',
  18,
  'bDAI'
);

beforeAll(async () => {
  avalanche = Avalanche.getInstance('avalanche');
  patchEVMNonceManager(avalanche.nonceManager);
  await avalanche.init();
  openocean = Openocean.getInstance('avalanche', 'avalanche');
  await openocean.init();
});

describe('verify Openocean estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    const expectedTrade = await openocean.estimateSellTrade(
      USDC,
      WAVAX,
      BigNumber.from((10 ** USDC.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    await expect(async () => {
      await openocean.estimateSellTrade(
        USDC,
        bDAI,
        BigNumber.from((10 ** USDC.decimals).toString())
      );
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Openocean estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    const expectedTrade = await openocean.estimateBuyTrade(
      USDC,
      WAVAX,
      BigNumber.from((10 ** WAVAX.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    await expect(async () => {
      await openocean.estimateBuyTrade(
        USDC,
        bDAI,
        BigNumber.from((10 ** bDAI.decimals).toString())
      );
    }).rejects.toThrow(UniswapishPriceError);
  });
});
