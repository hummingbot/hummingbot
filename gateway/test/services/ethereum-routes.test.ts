import request from 'supertest';
import { app } from '../../src/app';
import { Ethereum } from '../../src/chains/ethereum/ethereum';
import * as transactionOutOfGas from './fixtures/transaction-out-of-gas.json';
import * as transactionOutOfGasReceipt from './fixtures/transaction-out-of-gas-receipt.json';
import * as transactionUnconfirmedReceipt from './fixtures/transaction-unconfirmed-receipt.json';

const OUT_OF_GAS_ERROR_CODE = 1003;

describe('Eth endpoints', () => {
  let eth: Ethereum;
  beforeAll(async () => {
    eth = Ethereum.getInstance();
    await eth.init();
  });
  it('should get an OUT of GAS error for failed out of gas transactions', async () => {
    eth.getTransaction = jest.fn().mockReturnValue(transactionOutOfGas);
    eth.getTransactionReceipt = jest
      .fn()
      .mockReturnValue(transactionOutOfGasReceipt);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(OUT_OF_GAS_ERROR_CODE);
  });

  it('should get a null in receipt for unconfirmed transactions', async () => {
    eth.getTransactionReceipt = jest
      .fn()
      .mockReturnValue(transactionUnconfirmedReceipt);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.receipt).toEqual(null);
  });
});
