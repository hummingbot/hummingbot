import { logger, errors } from 'ethers';
import { Ethereum } from '../../src/chains/ethereum/ethereum';
import { logger as gatewayLogger } from '../../src/services/logger';

jest.setTimeout(60000); // run for 1 mins

describe('Eth node network errors', () => {
  let eth: Ethereum;
  const errorList: errors[] = [
    errors.SERVER_ERROR,
    errors.TIMEOUT,
    errors.NETWORK_ERROR,
    errors.INSUFFICIENT_FUNDS,
    errors.TRANSACTION_REPLACED,
  ];
  beforeAll(async () => {
    eth = Ethereum.getInstance();
    await eth.init();
    await eth.provider.ready;
  });
  it('should get specific node errors', (done) => {
    function assert(data: any) {
      expect(errorList).toContain(data.code);
      errorList.splice(errorList.indexOf(data.code), 1);
      if (errorList.length === 0) done();
    }

    for (const err of errorList) {
      eth.provider.emit('error', logger.makeError('Test node error', err));
    }

    gatewayLogger.on('data', assert.bind(this));
  });
});
