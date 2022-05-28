import 'jest-extended';
import { requestHarmony as request } from './test.base';

const ALLOWANCE = '5000000';

let publicKey: string;
if (process.env.ETH_PUBLIC_KEY && process.env.ETH_PUBLIC_KEY !== '') {
  publicKey = process.env.ETH_PUBLIC_KEY;
} else {
  console.log(
    'Please define the env variable ETH_PUBLIC_KEY in order to run the tests.'
  );
  process.exit(1);
}

const sleep = (ms: number) => {
  return new Promise((resolve) => setTimeout(resolve, ms));
};

jest.setTimeout(300000); // run for 5 mins

export const unitTests = async () => {
  test('harmony routes', async () => {
    await harmonyTests();
  });
};

const network = 'mainnet'; // Replace with `testnet` for testing on test net

export const harmonyTests = async (
  connector: string = '0x1b02da8cb0d097eb8d57a175b88c7d8b47997506', // Sushiswap router address
  tokens: string[] = ['WONE', 'USDC']
) => {
  console.log('\nStarting Harmony tests');
  console.log('***************************************************');
  console.log('Token symbols used in tests: ', tokens);
  expect(tokens.length).toEqual(2);

  // Check wallet for public key is added
  console.log('Checking wallet has been added...');
  const wallets = await request('GET', '/wallet', {});
  console.log(wallets);
  for (const chain of wallets) {
    if (chain.chain === 'harmony')
      expect(chain.walletAddresses).toContain(publicKey);
  }

  // call /
  console.log('Checking status of gateway server...');
  const result = await request('GET', '/', {});
  // confirm expected response
  console.log(result);
  expect(result.status).toEqual('ok');

  // call /balances
  console.log('Checking balances...');
  const balancesResponse = await request('POST', '/network/balances', {
    address: publicKey,
    chain: 'harmony',
    network,
    tokenSymbols: tokens,
  });
  // confirm and save balances
  const balances = balancesResponse.balances;
  console.log(balances);
  expect(parseFloat(balances['WONE'])).toBeDefined();
  expect(parseFloat(balances['USDC'])).toBeDefined();

  // call /balances with invalid token symbol
  // confirm expected error message
  console.log('calling balances with invalid token symbols ABC and XYZ...');
  const balancesResponse1 = await request('POST', '/network/balances', {
    address: publicKey,
    chain: 'harmony',
    network,
    tokenSymbols: ['ABC', 'XYZ'],
  });
  expect(balancesResponse1).toBeUndefined();

  // call /allowances
  // confirm and save allowances
  console.log('checking initial allowances...');
  const allowancesResponse1 = await request('POST', '/evm/allowances', {
    address: publicKey,
    chain: 'harmony',
    network,
    tokenSymbols: tokens,
    spender: connector,
  });
  let allowances = allowancesResponse1.approvals;
  console.log(allowances);

  // TODO: For some reason, the approve amount is not working

  for (const token of [tokens[0], tokens[1]]) {
    // call /approve on each token
    console.log(`Resetting allowance for ${token} to ${ALLOWANCE}...`);
    const nonce = await request('POST', '/evm/nonce', {
      address: publicKey,
      chain: 'harmony',
      network,
    });
    console.log(`Nonce: ${nonce.nonce}`);
    const approve1 = await request('POST', '/evm/approve', {
      address: publicKey,
      chain: 'harmony',
      network,
      token: token,
      spender: connector,
      amount: ALLOWANCE,
      nonce: nonce.nonce,
    });
    console.log(approve1);
    while (allowances[token] !== approve1.amount) {
      console.log(
        'Waiting for atleast 1 block time (i.e 13 secs) to give time for approval to be mined.'
      );
      await sleep(13000);
      // confirm that allowance changed correctly
      console.log('Rechecking allowances to confirm approval...');
      const allowancesResponse2 = await request('POST', '/evm/allowances', {
        address: publicKey,
        chain: 'harmony',
        network,
        tokenSymbols: tokens,
        spender: connector,
      });
      allowances = allowancesResponse2.approvals;
      console.log(allowances);
    }
  }

  // call /approve with invalid spender address
  console.log('Trying to approve for invalid contract...');
  const approve3 = await request('POST', '/evm/approve', {
    address: publicKey,
    chain: 'harmony',
    network,
    token: tokens[0],
    spender: 'nill',
  });
  console.log(approve3);
  // confirm expected error message
  expect(approve3).toBeUndefined();

  // call /approve with invalid token symbol
  console.log('Trying to approve invalid token ABC...');
  const approve4 = await request('POST', '/evm/approve', {
    address: publicKey,
    chain: 'harmony',
    network,
    token: 'ABC',
    spender: connector,
  });
  console.log(approve4);
  // confirm expected error message
  expect(approve4).toBeUndefined();

  // call /approve with invalid amount
  console.log('Trying to approve invalid amount...');
  const approve5 = await request('POST', '/evm/approve', {
    address: publicKey,
    chain: 'harmony',
    network,
    token: tokens[0],
    connector: connector,
    amount: 'number',
  });
  console.log(approve5);
  // confirm expected error message
  expect(approve5).toBeUndefined();
};

(async () => {
  await unitTests();
})();
