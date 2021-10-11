import { Ethereum } from '../../src/chains/ethereum/ethereum';

describe('Eth block listener test', () => {
  let eth: Ethereum;
  beforeAll(async () => {
    eth = Ethereum.getInstance();
    await eth.init();
  });
  it('block event should be registered', async () => {
    expect(eth.provider._events.length).toBeGreaterThanOrEqual(1);
  });
  it('block number should be updated', async () => {
    eth.on_new_block(100);
    expect(eth.blockNumber).toEqual(100);
  });
});
