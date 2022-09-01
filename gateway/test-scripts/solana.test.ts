import 'jest-extended';
import {
  privateKey,
  publicKey,
} from '../test/chains/solana/solana.validators.test';
import { request } from './test.base';

// constants
const TOKENS = ['SOL', 'RAY']; // change second token, if RAY token account is already initialized

jest.setTimeout(300000); // run for 5 mins

export const unitTests = async () => {
  test('solana routes', async () => {
    await solTests(TOKENS);
  });
};

export const solTests = async (tokens: string[] = []) => {
  console.log('\nStarting SOL tests');
  console.log('***************************************************');
  console.log('Token symbols used in tests: ', tokens);
  expect(tokens.length).toEqual(2);

  // call /
  console.log('Checking status of gateway server...');
  const result = await request('GET', '/', {});
  // confirm expected response
  console.log(result);
  expect(result.status).toEqual('ok');

  // Check wallet for public key is added
  console.log(`Checking if wallet ${publicKey} has been added...`);
  const wallets = await request('GET', '/wallet/', {});
  console.log(wallets);
  let alreadyAdded = false;
  for (const chain of wallets) {
    if (chain.chain === 'solana' && publicKey in chain.walletAddresses) {
      console.log(`Wallet ${publicKey} has been already added...`);
      alreadyAdded = true;
    }
  }
  if (alreadyAdded === false) {
    console.log(`Adding wallet ${publicKey}...`);
    await request('POST', '/wallet/add', {
      privateKey: privateKey,
      chainName: 'solana',
    });
  }

  // call /balances
  console.log('Checking balances...');
  const balancesResponse = await request('GET', '/solana/balances', {
    address: publicKey,
    tokenSymbols: tokens,
  });
  // confirm and save balances
  const balances = balancesResponse.balances;
  console.log(balances);
  expect(parseFloat(balances.SOL)).toBeGreaterThanOrEqual(0.0); // that's how much we need for new token accounts

  // call /balances with invalid token symbol
  // confirm expected error message
  console.log('calling balances with invalid token symbols 15B and LLL...');
  const balancesResponse1 = await request('GET', '/solana/balances', {
    tokenSymbols: ['15B', 'LLL'],
  });
  expect(balancesResponse1).toBeUndefined();

  // call /allowances
  // confirm and save allowances
  console.log(`checking associated token account for token ${tokens[1]}...`);
  const getTokenResponse = await request('GET', '/solana/token', {
    token: tokens[1],
    address: publicKey,
  });
  console.log(getTokenResponse);
  const associatedTokenAccount = getTokenResponse?.accountAddress;
  expect(associatedTokenAccount).toBeUndefined();

  // call /approve with invalid spender address
  console.log('Trying to approve for invalid contract...');
  const postTokenInvalid1 = await request('POST', '/solana/token', {
    token: tokens[1],
    address: 'nill',
  });
  console.log(postTokenInvalid1);
  // confirm expected error message
  expect(postTokenInvalid1).toBeUndefined();

  // call /approve with invalid token symbol
  console.log('Trying to approve invalid token 15B...');
  const postTokenInvalid2 = await request('POST', '/solana/token', {
    token: '15B',
    address: publicKey,
  });
  console.log(postTokenInvalid2);
  // confirm expected error message
  expect(postTokenInvalid2).toBeUndefined();
};

(async () => {
  await unitTests();
})();
