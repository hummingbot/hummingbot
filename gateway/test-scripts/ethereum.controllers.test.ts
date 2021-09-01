import { approve, ethereum } from '../src/chains/ethereum/ethereum.controllers';
const SPENDER = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D';

let privateKey: string;
if (process.env.ETH_PRIVATE_KEY && process.env.ETH_PRIVATE_KEY !== '') {
  privateKey = process.env.ETH_PRIVATE_KEY;
} else {
  console.log(
    'Please define the env variable ETH_PRIVATE_KEY in order to run the tests.'
  );
  process.exit(1);
}

describe('Transaction is out of gas', () => {
  it('should fail', async () => {
    ethereum.approveERC20 = jest.fn().mockReturnValue('salio todo bien');
    const res = await approve(SPENDER, privateKey, 'DAI');
    expect(res).toEqual(200);
  });
});
