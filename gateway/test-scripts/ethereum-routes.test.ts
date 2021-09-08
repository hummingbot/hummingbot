import request from 'supertest';
import { app } from '../src/app';
import { Ethereum } from '../src/chains/ethereum/ethereum';
import * as transactionOutOfGas from './fixtures/transaction-out-of-gas.json';

describe('Eth endpoints', () => {
  let eth: Ethereum;
  beforeAll(async () => {
    eth = Ethereum.getInstance();
    await eth.init();
  });
  it('should get a 200 OK on /', async () => {
    eth.getTransactionReceipt = jest.fn().mockReturnValue(transactionOutOfGas);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.confirmed).toEqual(true);
  });
});
