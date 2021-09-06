import request from 'supertest';
import { app } from '../src/app';
import { ethereum } from '../src/chains/ethereum/ethereum.controllers';

describe('Eth endpoints', () => {
  it('should get a 200 OK on /', async () => {
    ethereum.approveERC20 = jest.fn().mockReturnValue('OK');
    const res = await request(app).post('/eth/approve').send({
      privateKey:
        '678ae8f74b6d8fdbb1c73059a63ece83c34e83daf73b0cbeaf7ff9c185f002c6',
      spender: '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
      token: 'DAI',
    });
    console.log(res.body)
    expect(res.statusCode).toEqual(200);
  });

  it('should get a 200 OK on /', async () => {
    ethereum.approveERC20 = jest.fn().mockReturnValue('OK');
    const res = await request(app).post('/eth/approve').send({
      privateKey:
        '678ae8f74b6d8fdbb1c73059a63ece83c34e83daf73b0cbeaf7ff9c185f002c6',
      spender: '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
      token: 'DAI',
    });
    console.log(res.body)
    expect(res.statusCode).toEqual(200);
  });
});
