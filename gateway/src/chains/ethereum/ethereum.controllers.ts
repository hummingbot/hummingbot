import { Ethereum } from './ethereum';
import { constants, Wallet, utils, BigNumber } from 'ethers';
import { ConfigManager } from '../../services/config-manager';
import { latency, bigNumberWithDecimalToStr } from '../../services/base';

export const ethereum = new Ethereum();

export async function approve(
  spender: string,
  privateKey: string,
  token: string,
  amount?: BigNumber | string
) {
  if (!ethereum.ready()) await ethereum.init();
  const initTime = Date.now();
  let wallet: Wallet;
  try {
    wallet = ethereum.getWallet(privateKey);
  } catch (err) {
    throw new Error(`Error getting wallet ${err}`);
  }
  const fullToken = ethereum.getTokenBySymbol(token);
  if (!fullToken) {
    throw new Error(`Token "${token}" is not supported`);
  }
  amount = amount
    ? utils.parseUnits(amount.toString(), fullToken.decimals)
    : constants.MaxUint256;

  // call approve function
  let approval;
  try {
    approval = await ethereum.approveERC20(
      wallet,
      spender,
      fullToken.address,
      amount
    );
  } catch (err) {
    approval = JSON.stringify(err);
  }

  return {
    network: ConfigManager.config.ETHEREUM_CHAIN,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    tokenAddress: fullToken.address,
    spender: spender,
    amount: bigNumberWithDecimalToStr(amount, fullToken.decimals),
    approval: approval,
  };
}
