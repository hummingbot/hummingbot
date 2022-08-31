import 'jest-extended';
import {
  privateKey,
  publicKey,
} from '../test/chains/cosmos/cosmos.validators.test';
import { request } from './test.base';

// constants
const TOKENS = ['ATOM'];

jest.setTimeout(300000); // run for 5 mins

export const unitTests = async () => {
  test('cosmos routes', async () => {
    await cosmosTests(TOKENS);
  });
};

export const cosmosTests = async (tokens: string[] = []) => {
  console.log('\nStarting Cosmos tests');
  console.log('***************************************************');
  console.log('Token symbols used in tests: ', tokens);
  expect(tokens.length).toEqual(1);

  // call /
  console.log('Checking status of gateway server...');
  const result = await request('GET', '/', {});
  // confirm expected response
  console.log(result);
  expect(result.status).toEqual('ok');

  // Check wallet for public key is added
  console.log(`Checking if wallet ${publicKey} has been added...`);
  const wallets = await request('GET', '/wallet/', {});
  let alreadyAdded = false;
  for (const chain of wallets) {
    if (chain.chain === 'cosmos' && publicKey in chain.walletAddresses) {
      console.log(`Wallet ${publicKey} has been already added...`);
      alreadyAdded = true;
    }
  }
  if (alreadyAdded === false) {
    console.log(`Adding wallet ${publicKey}...`);
    await request('POST', '/wallet/add', {
      privateKey: privateKey,
      chain: 'cosmos',
      network: 'mainnet',
    });
  }

  // call /balances with invalid token symbol
  // confirm expected error message
  console.log('calling balances with invalid token symbols 15B and LLL...');
  const balancesResponse1 = await request('POST', '/cosmos/balances', {
    address: publicKey,
    tokenSymbols: ['15B', 'LLL'],
  });
  expect(balancesResponse1).toBeUndefined();

  // call /balances
  console.log('Checking balances...');
  const balancesResponse = await request('POST', '/cosmos/balances', {
    address: publicKey,
    tokenSymbols: tokens,
  });
  // confirm and save balances
  const balances = balancesResponse.balances;
  expect(parseFloat(balances.ATOM)).toBeGreaterThanOrEqual(0.0);
};

(async () => {
  await unitTests();
})();
