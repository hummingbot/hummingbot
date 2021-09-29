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
  return receipt
    ? {
        ...receipt,
        gasUsed: receipt.gasUsed.toString(),
        cumulativeGasUsed: receipt.cumulativeGasUsed.toString(),
      }
    : null;
};

export async function poll(txHash: string) {
  const initTime = Date.now();
  const txData = await ethereum.getTransaction(txHash);
  let txReceipt, txStatus;
  if (!txData) {
    // tx didn't reach the mempool
    txReceipt = null;
    txStatus = -1;
  } else {
    txReceipt = await ethereum.getTransactionReceipt(txHash);
    if (txReceipt === null || txReceipt.blockNumber === 0) {
      // tx is in the mempool
      txReceipt = null;
      txStatus = -1;
    } else {
      // tx has been processed
      txStatus = typeof txReceipt.status === 'number' ? txReceipt.status : -1;
      if (txStatus === 0) {
        const gasUsed = BigNumber.from(txReceipt.gasUsed).toNumber();
        const gasLimit = BigNumber.from(txData.gasLimit).toNumber();
        if (gasUsed / gasLimit > 0.9)
          throw new GatewayError(503, 1003, 'Transaction out of gas.');
      }
    }
  }
  return {
    network: ConfigManager.config.ETHEREUM_CHAIN,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    txHash,
    txStatus,
    txData,
    txReceipt: toEthereumTransactionReceipt(txReceipt),
  };
}
