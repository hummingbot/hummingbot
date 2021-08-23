import { ConfigManager } from '../src/services/config-manager';
import axios from 'axios';
import fs from 'fs';
import https from 'https';
import 'jest-extended';

const certPath = ConfigManager.config.CERT_PATH.replace(/\/$/, '');
const host = 'localhost';
const port = ConfigManager.config.PORT;
const uniswapContract = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D';

let privateKey: string;
if (process.env.ETH_PRIVATE_KEY && process.env.ETH_PRIVATE_KEY !== '') {
  privateKey = process.env.ETH_PRIVATE_KEY;
} else {
  console.log(
    'Please define the env variable ETH_PRIVATE_KEY in order to run the tests.'
  );
  process.exit(1);
}

const httpsAgent = axios.create({
  httpsAgent: new https.Agent({
    ca: fs.readFileSync(certPath.concat('/ca_cert.pem'), {
      encoding: 'utf-8',
    }),
    cert: fs.readFileSync(certPath.concat('/client_cert.pem'), {
      encoding: 'utf-8',
    }),
    key: fs.readFileSync(certPath.concat('/client_key.pem'), {
      encoding: 'utf-8',
    }),
    host: host,
    port: port,
    requestCert: true,
    rejectUnauthorized: false,
  }),
});

type method = 'GET' | 'POST';

const request = async (
  method: method,
  path: string,
  params: Record<string, any>
) => {
  try {
    let response;
    const gatewayAddress = `https://${host}:${port}`;
    if (method === 'GET') {
      return httpsAgent.get(gatewayAddress + path);
    } else {
      return httpsAgent.post(gatewayAddress + path, params);
    }
    return response.data;
  } catch (err) {
    console.log(`${path} - ${err}`);
  }
};

const ethTests = async () => {
  test('ethereum routes', async () => {
    const gatewayPingResult = await request('GET', '/', {});
    expect(gatewayPingResult.data).toEqual('ok');

    const gatewayEthPingResult = await request('GET', '/eth', {});
    expect(gatewayEthPingResult.data.connection).toEqual(true);

    // ETH is always queried even if not included as a token symbol
    const gatewayEthBalanceResult = await request('POST', '/eth/balances', {
      privateKey: privateKey,
      tokenSymbols: ['DAI', 'WETH'],
    });
    expect(Object.keys(gatewayEthBalanceResult.data.balances).length).toEqual(
      3
    );

    const gatewayEthApproveResult = await request('POST', '/eth/approve', {
      privateKey: privateKey,
      spender: uniswapContract,
      token: 'DAI',
    });

    const txHash = gatewayEthApproveResult.data.approval.hash;

    const gatewayEthPollResult = await request('POST', '/eth/poll', {
      txHash: txHash,
    });

    console.log(gatewayEthPollResult);
  });
};

(async () => {
  await ethTests();
})();
