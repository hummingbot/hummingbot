import fs = require('fs');
import path = require('path');
import https = require('https');
import { publicKey } from '../test/chains/solana/solana.validators.test';
import axios from 'axios';
import { ConfigManagerV2 } from '../src/services/config-manager-v2';

type method = 'GET' | 'POST';

const confV2 = new ConfigManagerV2(path.join(__dirname, '../conf/root.yml'));
const certPath = path.dirname(confV2.get('ssl.certificatePath'));
const host = 'localhost';
const port = confV2.get('server.port');

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

export const request = async (
  method: method,
  path: string,
  params: Record<string, any>
) => {
  try {
    let response;
    const gatewayAddress = `https://${host}:${port}`;
    if (method === 'GET') {
      response = await httpsAgent.get(gatewayAddress + path);
    } else {
      params.address = publicKey;
      response = await httpsAgent.post(gatewayAddress + path, params);
    }
    return response.data;
  } catch (err) {
    console.log(`${method} ${path} - ${err}`);
  }
};

export const requestHarmony = async (
  method: method,
  path: string,
  params: Record<string, any>
) => {
  try {
    let response;
    const gatewayAddress = `https://${host}:${port}`;
    if (method === 'GET') {
      response = await httpsAgent.get(gatewayAddress + path);
    } else {
      response = await httpsAgent.post(gatewayAddress + path, params);
    }
    return response.data;
  } catch (err) {
    console.log(`${method} ${path} - ${err}`);
  }
};
