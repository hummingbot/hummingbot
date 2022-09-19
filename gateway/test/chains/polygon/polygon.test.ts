import { Polygon } from '../../../src/chains/polygon/polygon';
import { unpatch } from '../../services/patch';
import { patchEVMNonceManager } from '../../evm.nonce.mock';
let polygon: Polygon;

beforeAll(async () => {
  polygon = Polygon.getInstance('mumbai');

  patchEVMNonceManager(polygon.nonceManager);

  await polygon.init();
});

beforeEach(() => {
  patchEVMNonceManager(polygon.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await polygon.close();
});

describe('public get', () => {
  it('gasPrice', async () => {
    expect(polygon.gasPrice).toEqual(100);
  });

  it('native token', async () => {
    expect(polygon.nativeTokenSymbol).toEqual('MATIC');
  });

  it('chain', async () => {
    expect(polygon.chain).toEqual('mumbai');
  });

  it('getSpender', async () => {
    expect(
      polygon.getSpender('0xd0A1E359811322d97991E03f863a0C30C2cF029C')
    ).toEqual('0xd0A1E359811322d97991E03f863a0C30C2cF029C');
  });
});
