import request from 'supertest';
import { logger, errors } from 'ethers';
import { patch, unpatch } from './patch';
import { app } from '../../src/app';
import { Ethereum } from '../../src/chains/ethereum/ethereum';
import * as transactionOutOfGas from './fixtures/transaction-out-of-gas.json';
import * as transactionOutOfGasReceipt from './fixtures/transaction-out-of-gas-receipt.json';

const OUT_OF_GAS_ERROR_CODE = 1003;

describe('Eth endpoints', () => {
  let eth: Ethereum;
  beforeAll(async () => {
    eth = Ethereum.getInstance();
    await eth.init();
  });
  afterEach(unpatch);

  it('should get an OUT of GAS error for failed out of gas transactions', async () => {
    patch(eth, 'getTransaction', () => transactionOutOfGas);
    patch(eth, 'getTransactionReceipt', () => transactionOutOfGasReceipt);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(OUT_OF_GAS_ERROR_CODE);
  });

  it('should get a null in txReceipt for Tx in the mempool', async () => {
    patch(eth, 'getTransaction', () => transactionOutOfGas);
    patch(eth, 'getTransactionReceipt', () => null);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toEqual(null);
    expect(res.body.txData).toBeDefined();
  });

  it('should get a null in txReceipt and txData for Tx that didnt reach the mempool and TxReceipt is null', async () => {
    patch(eth, 'getTransaction', () => null);
    patch(eth, 'getTransactionReceipt', () => null);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toEqual(null);
    expect(res.body.txData).toEqual(null);
  });

  it('should get timeout error', async () => {
    patch(eth, 'getTransaction', () => {
      return logger.throwError(errors.TIMEOUT, errors.TIMEOUT);
    });
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(500);
    expect(res.body.message).toEqual(expect.stringContaining(errors.TIMEOUT));
  });

  it('should get network error', async () => {
    patch(eth, 'getTransaction', () => {
      return logger.throwError(errors.NETWORK_ERROR, errors.NETWORK_ERROR);
    });
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(500);
    expect(res.body.message).toEqual(
      expect.stringContaining(errors.NETWORK_ERROR)
    );
  });

  it('should get server error', async () => {
    patch(eth, 'getTransaction', () => {
      return logger.throwError(errors.SERVER_ERROR, errors.SERVER_ERROR);
    });
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(500);
    expect(res.body.message).toEqual(
      expect.stringContaining(errors.SERVER_ERROR)
    );
  });
});
