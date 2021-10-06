import { Ethereum } from './ethereum';
import ethers, { constants, Wallet, utils, BigNumber } from 'ethers';
import { ConfigManager } from '../../services/config-manager';
import { latency, bigNumberWithDecimalToStr } from '../../services/base';
import { GatewayError } from '../../services/error-handler';

export const ethereum = Ethereum.getInstance();

export async function approve(
  spender: string,
  privateKey: string,
  token: string,
  amount?: BigNumber | string,
  nonce?: number
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
  const approval = await ethereum.approveERC20(
    wallet,
    spender,
    fullToken.address,
    amount,
    nonce
  );

  return {
    network: ConfigManager.config.ETHEREUM_CHAIN,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    tokenAddress: fullToken.address,
    spender: spender,
    amount: bigNumberWithDecimalToStr(amount, fullToken.decimals),
    nonce: approval.nonce,
    approval: approval,
  };
}

// TransactionReceipt from ethers uses BigNumber which is not easy to interpret directly from JSON.
// Transform those BigNumbers to string and pass the rest of the data without changes.

export interface EthereumTransactionReceipt
  extends Omit<
    ethers.providers.TransactionReceipt,
    'gasUsed' | 'cumulativeGasUsed'
  > {
  gasUsed: string;
  cumulativeGasUsed: string;
}

const toEthereumTransactionReceipt = (
  receipt: ethers.providers.TransactionReceipt | null
): EthereumTransactionReceipt | null => {
  if (receipt) {
    return {
      ...receipt,
      gasUsed: receipt.gasUsed.toString(),
      cumulativeGasUsed: receipt.cumulativeGasUsed.toString(),
    };
  }

  return null;
};

export async function poll(txHash: string) {
  const initTime = Date.now();
  const receipt = ethereum.getTransactionReceipt(txHash);
  const confirmed = !!receipt && !!receipt.blockNumber;

  if (receipt && receipt.status === 0) {
    const transaction = await ethereum.getTransaction(txHash);
    const gasUsed = BigNumber.from(receipt.gasUsed).toNumber();
    const gasLimit = BigNumber.from(transaction.gasLimit).toNumber();
    if (gasUsed / gasLimit > 0.9)
      throw new GatewayError(503, 1003, 'Transaction out of gas.');
  }

  return {
    network: ConfigManager.config.ETHEREUM_CHAIN,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    txHash,
    confirmed,
    receipt: toEthereumTransactionReceipt(receipt),
  };
}
