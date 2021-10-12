import { Ethereum } from '../../src/chains/ethereum/ethereum';

describe('Eth block listener test', () => {
  let eth: Ethereum;
  beforeAll(async () => {
    eth = Ethereum.getInstance();
    await eth.init();
    await eth.provider.ready;
  });
  it('block event should be registered', (done) => {
    function processNewBlock(blockNumber: number) {
      expect(blockNumber).toBeGreaterThan(1);
      done();
    }

    eth.onNewBlock(processNewBlock);
  });
});
