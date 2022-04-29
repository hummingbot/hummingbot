import request from 'supertest';
import { gatewayApp } from '../../../../src/app';
import { Avalanche } from '../../../../src/chains/avalanche/avalanche';
import { Openocean } from '../../../../src/connectors/openocean/openocean';
let avalanche: Avalanche;
let openocean: Openocean;

const address: string = '0x00000000000000000000000000000000000';
const privateKey = '0000000000000000000000000000000000000000000000000000000000000002';

beforeAll(async () => {
  avalanche = Avalanche.getInstance('avalanche');
  await avalanche.init();
  openocean = Openocean.getInstance('avalanche', 'avalanche');
  await openocean.init();

  const passphrase = 'waylin_args_passphrase';
  process.argv.push(`--passphrase=${passphrase}`);

  await request(gatewayApp)
    .post(`/wallet/add`)
    .send({
      privateKey: privateKey,
      chain: 'avalanche',
      network: 'avalanche',
    })
    .expect('Content-Type', /json/)
    .expect(200);

  // process.argv.pop();
});

describe('POST /amm/price', () => {
  it('should return 200 for BUY', async () => {
    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'WAVAX',
        base: 'USDC',
        amount: '0.01',
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.amount).toEqual('0.010000');
        expect(res.body.rawAmount).toEqual('10000');
      });
  });

  it('should return 200 for SELL', async () => {
    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'USDC',
        base: 'WAVAX',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.amount).toEqual('10000.000000000000000000');
        expect(res.body.rawAmount).toEqual('10000000000000000000000');
      });
  });

  it('should return 500 for unrecognized quote symbol', async () => {
    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'USDC',
        base: 'bDAI',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 for unrecognized base symbol', async () => {
    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'USDC',
        base: 'bDAI',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});

describe('POST /amm/trade', () => {
  it('should return 200 for BUY', async () => {
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'USDC',
        base: 'WAVAX',
        amount: '10000',
        address,
        side: 'BUY',
        nonce: 21,
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.nonce).toEqual(21);
      });
  });

  it('should return 200 for BUY without nonce parameter', async () => {
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'USDC',
        base: 'WAVAX',
        amount: '10000',
        address,
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 200 for SELL', async () => {
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'USDC',
        base: 'WAVAX',
        amount: '0.001',
        address,
        side: 'SELL',
        nonce: 21,
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        console.log(res.body);
        expect(res.body.nonce).toEqual(21);
      });
  });

  // it('should return 404 when parameters are incorrect', async () => {
  //   await request(gatewayApp)
  //     .post(`/amm/trade`)
  //     .send({
  //       chain: 'avalanche',
  //       network: 'avalanche',
  //       connector: 'openocean',
  //       quote: 'USDC',
  //       base: 'WAVAX',
  //       amount: 10000,
  //       address: 'da8',
  //       side: 'comprar',
  //     })
  //     .set('Accept', 'application/json')
  //     .expect(404);
  // });
  //
  // it('should return 500 when base token is unknown', async () => {
  //   await request(gatewayApp)
  //     .post(`/amm/trade`)
  //     .send({
  //       chain: 'avalanche',
  //       network: 'avalanche',
  //       connector: 'openocean',
  //       quote: 'USDC',
  //       base: 'bDAI',
  //       amount: '10000',
  //       address,
  //       side: 'BUY',
  //       nonce: 21,
  //       maxFeePerGas: '5000000000',
  //       maxPriorityFeePerGas: '5000000000',
  //     })
  //     .set('Accept', 'application/json')
  //     .expect(500);
  // });
  //
  // it('should return 500 when quote token is unknown', async () => {
  //   await request(gatewayApp)
  //     .post(`/amm/trade`)
  //     .send({
  //       chain: 'avalanche',
  //       network: 'avalanche',
  //       connector: 'openocean',
  //       quote: 'bDAI',
  //       base: 'USDC',
  //       amount: '10000',
  //       address,
  //       side: 'BUY',
  //       nonce: 21,
  //       maxFeePerGas: '5000000000',
  //       maxPriorityFeePerGas: '5000000000',
  //     })
  //     .set('Accept', 'application/json')
  //     .expect(500);
  // });
  //
  // it('should return 200 for SELL with limitPrice', async () => {
  //   await request(gatewayApp)
  //     .post(`/amm/trade`)
  //     .send({
  //       chain: 'avalanche',
  //       network: 'avalanche',
  //       connector: 'openocean',
  //       quote: 'USDC',
  //       base: 'WAVAX',
  //       amount: '10000',
  //       address,
  //       side: 'SELL',
  //       nonce: 21,
  //       limitPrice: '9',
  //     })
  //     .set('Accept', 'application/json')
  //     .expect(200);
  // });
  //
  // it('should return 200 for BUY with limitPrice', async () => {
  //   await request(gatewayApp)
  //     .post(`/amm/trade`)
  //     .send({
  //       chain: 'avalanche',
  //       network: 'avalanche',
  //       connector: 'openocean',
  //       quote: 'USDC',
  //       base: 'WAVAX',
  //       amount: '10000',
  //       address,
  //       side: 'BUY',
  //       nonce: 21,
  //       limitPrice: '999999999999999999999',
  //     })
  //     .set('Accept', 'application/json')
  //     .expect(200);
  // });
  //
  // it('should return 500 for SELL with price higher than limitPrice', async () => {
  //   await request(gatewayApp)
  //     .post(`/amm/trade`)
  //     .send({
  //       chain: 'avalanche',
  //       network: 'avalanche',
  //       connector: 'openocean',
  //       quote: 'USDC',
  //       base: 'WAVAX',
  //       amount: '10000',
  //       address,
  //       side: 'SELL',
  //       nonce: 21,
  //       limitPrice: '99999999999',
  //     })
  //     .set('Accept', 'application/json')
  //     .expect(500);
  // });
  //
  // it('should return 500 for BUY with price less than limitPrice', async () => {
  //   await request(gatewayApp)
  //     .post(`/amm/trade`)
  //     .send({
  //       chain: 'avalanche',
  //       network: 'avalanche',
  //       connector: 'openocean',
  //       quote: 'USDC',
  //       base: 'WAVAX',
  //       amount: '10000',
  //       address,
  //       side: 'BUY',
  //       nonce: 21,
  //       limitPrice: '9',
  //     })
  //     .set('Accept', 'application/json')
  //     .expect(500);
  // });
});
