import { Ethereum } from '../../src/chains/ethereum/ethereum';
import { patch, unpatch } from './patch';

describe('Eth block listener test', () => {
  let eth: Ethereum;
  beforeAll(async () => {
    eth = Ethereum.getInstance('kovan');
    patch(eth, 'loadTokens', async () => {
      return;
    });
    await eth.init();
    await eth.provider.ready;
  });

  afterAll(() => {
    unpatch();
  });

  it('block event should be registered', (done) => {
    function processNewBlock(blockNumber: number) {
      expect(blockNumber).toBeGreaterThan(1);
      done();
    }

    eth.onNewBlock(processNewBlock);
  });

  // this has undeterministic behavior
  // it('request counter works', (done) => {
  //   function processDebugMsg(msg: any) {
  //     expect(msg.action).toEqual('request');
  //     done();
  //   }

  //   eth.onDebugMessage(processDebugMsg);
  //   // this is the second request
  //   eth.provider.emit('debug', { action: 'request' });
  //   expect(eth.requestCount).toEqual(2);
  // });
});
