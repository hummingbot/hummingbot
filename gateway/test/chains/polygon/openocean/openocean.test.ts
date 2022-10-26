import { patchEVMNonceManager } from '../../../evm.nonce.mock';

jest.useFakeTimers();
jest.setTimeout(30000);
import { Openocean } from '../../../../src/connectors/openocean/openocean';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import { Token } from '@uniswap/sdk';
import { BigNumber } from 'ethers';
import { Polygon } from '../../../../src/chains/polygon/polygon';

let polygon: Polygon;
let openocean: Openocean;

const USDC = new Token(
  137,
  '0x2791bca1f2de4661ed88a30c99a7a9449aa84174',
  6,
  'USDC'
);
const MATIC = new Token(
  137,
  '0x0000000000000000000000000000000000001010',
  18,
  'MATIC'
);
const USDK = new Token(
  137,
  '0xD07A7FAc2857901E4bEC0D89bBDAe764723AAB86',
  18,
  'USDK'
);

beforeAll(async () => {
  polygon = Polygon.getInstance('mainnet');
  patchEVMNonceManager(polygon.nonceManager);
  await polygon.init();
  openocean = Openocean.getInstance('polygon', 'mainnet');
  await openocean.init();
});

describe('verify Openocean estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    const expectedTrade = await openocean.estimateSellTrade(
      USDC,
      MATIC,
      BigNumber.from((10 ** USDC.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    await expect(async () => {
      await openocean.estimateSellTrade(
        USDC,
        USDK,
        BigNumber.from((10 ** USDC.decimals).toString())
      );
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Openocean estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    const expectedTrade = await openocean.estimateBuyTrade(
      USDC,
      MATIC,
      BigNumber.from((10 ** MATIC.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    await expect(async () => {
      await openocean.estimateBuyTrade(
        USDC,
        USDK,
        BigNumber.from((10 ** USDK.decimals).toString())
      );
    }).rejects.toThrow(UniswapishPriceError);
  });
});
