import ethers, {
  constants,
  Wallet,
  utils,
  BigNumber,
  Transaction,
} from 'ethers';
import { latency, bigNumberWithDecimalToStr } from '../../services/base';
import {
  HttpException,
  OUT_OF_GAS_ERROR_CODE,
  OUT_OF_GAS_ERROR_MESSAGE,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { tokenValueToString } from '../../services/base';
import { Token } from '../../services/ethereum-base';

import {
  EthereumAllowancesRequest,
  EthereumAllowancesResponse,
  EthereumApproveRequest,
  EthereumApproveResponse,
  EthereumBalanceResponse,
  EthereumBalanceRequest,
  EthereumCancelRequest,
  EthereumCancelResponse,
  EthereumNonceRequest,
  EthereumNonceResponse,
  EthereumPollRequest,
  EthereumPollResponse,
  EthereumTransactionReceipt,
  EthereumTransaction,
  EthereumTransactionResponse,
} from './ethereum.requests';
import { Ethereumish } from '../../services/ethereumish.interface';

export async function nonce(
  ethereum: Ethereumish,
  req: EthereumNonceRequest
): Promise<EthereumNonceResponse> {
  // get the address via the private key since we generally use the private
  // key to interact with gateway and the address is not part of the user config
  const wallet = ethereum.getWallet(req.privateKey);
  const nonce = await ethereum.nonceManager.getNonce(wallet.address);
  return { nonce };
}

export const getTokenSymbolsToTokens = (
  ethereum: Ethereumish,
  tokenSymbols: Array<string>
): Record<string, Token> => {
  const tokens: Record<string, Token> = {};

  for (let i = 0; i < tokenSymbols.length; i++) {
    const symbol = tokenSymbols[i];
    const token = ethereum.getTokenBySymbol(symbol);
    if (token) tokens[symbol] = token;
  }

  return tokens;
};

export async function allowances(
  ethereumish: Ethereumish,
  req: EthereumAllowancesRequest
): Promise<EthereumAllowancesResponse | string> {
  const initTime = Date.now();
  const wallet = ethereumish.getWallet(req.privateKey);
  const tokens = getTokenSymbolsToTokens(ethereumish, req.tokenSymbols);
  const spender = ethereumish.getSpender(req.spender);

  const approvals: Record<string, string> = {};
  await Promise.all(
    Object.keys(tokens).map(async (symbol) => {
      // instantiate a contract and pass in provider for read-only access
      const contract = ethereumish.getContract(
        tokens[symbol].address,
        ethereumish.provider
      );
      approvals[symbol] = tokenValueToString(
        await ethereumish.getERC20Allowance(
          contract,
          wallet,
          spender,
          tokens[symbol].decimals
        )
      );
    })
  );

  return {
    network: ethereumish.chain,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    spender: spender,
    approvals: approvals,
  };
}

export async function balances(
  ethereumish: Ethereumish,
  req: EthereumBalanceRequest
): Promise<EthereumBalanceResponse | string> {
  const initTime = Date.now();

  let wallet: Wallet;
  try {
    wallet = ethereumish.getWallet(req.privateKey);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }
  const tokens = getTokenSymbolsToTokens(ethereumish, req.tokenSymbols);
  const balances: Record<string, string> = {};
  if (req.tokenSymbols.includes(ethereumish.nativeTokenSymbol)) {
    balances[ethereumish.nativeTokenSymbol] = tokenValueToString(
      await ethereumish.getNativeBalance(wallet)
    );
  }
  await Promise.all(
    Object.keys(tokens).map(async (symbol) => {
      if (tokens[symbol] !== undefined) {
        const address = tokens[symbol].address;
        const decimals = tokens[symbol].decimals;
        // instantiate a contract and pass in provider for read-only access
        const contract = ethereumish.getContract(address, ethereumish.provider);
        const balance = await ethereumish.getERC20Balance(
          contract,
          wallet,
          decimals
        );
        balances[symbol] = tokenValueToString(balance);
      }
    })
  );

  if (!Object.keys(balances).length) {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  }

  return {
    network: ethereumish.chain,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances: balances,
  };
}

const toEthereumTransaction = (
  transaction: Transaction
): EthereumTransaction => {
  let maxFeePerGas = null;
  if (transaction.maxFeePerGas) {
    maxFeePerGas = transaction.maxFeePerGas.toString();
  }
  let maxPriorityFeePerGas = null;
  if (transaction.maxPriorityFeePerGas) {
    maxPriorityFeePerGas = transaction.maxPriorityFeePerGas.toString();
  }
  let gasLimit = null;
  if (transaction.gasLimit) {
    gasLimit = transaction.gasLimit.toString();
  }
  return {
    ...transaction,
    maxPriorityFeePerGas,
    maxFeePerGas,
    gasLimit,
    value: transaction.value.toString(),
  };
};

export async function approve(
  ethereumish: Ethereumish,
  req: EthereumApproveRequest
): Promise<EthereumApproveResponse> {
  const {
    amount,
    nonce,
    privateKey,
    token,
    maxFeePerGas,
    maxPriorityFeePerGas,
  } = req;
  const spender = ethereumish.getSpender(req.spender);
  const initTime = Date.now();
  let wallet: Wallet;
  try {
    wallet = ethereumish.getWallet(privateKey);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }
  const fullToken = ethereumish.getTokenBySymbol(token);
  if (!fullToken) {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + token,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  }
  const amountBigNumber = amount
    ? utils.parseUnits(amount, fullToken.decimals)
    : constants.MaxUint256;

  let maxFeePerGasBigNumber;
  if (maxFeePerGas) {
    maxFeePerGasBigNumber = BigNumber.from(maxFeePerGas);
  }
  let maxPriorityFeePerGasBigNumber;
  if (maxPriorityFeePerGas) {
    maxPriorityFeePerGasBigNumber = BigNumber.from(maxPriorityFeePerGas);
  }
  // instantiate a contract and pass in wallet, which act on behalf of that signer
  const contract = ethereumish.getContract(fullToken.address, wallet);

  // convert strings to BigNumber
  // call approve function
  const approval = await ethereumish.approveERC20(
    contract,
    wallet,
    spender,
    amountBigNumber,
    nonce,
    maxFeePerGasBigNumber,
    maxPriorityFeePerGasBigNumber,
    ethereumish.gasPrice
  );

  return {
    network: ethereumish.chain,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    tokenAddress: fullToken.address,
    spender: spender,
    amount: bigNumberWithDecimalToStr(amountBigNumber, fullToken.decimals),
    nonce: approval.nonce,
    approval: toEthereumTransaction(approval),
  };
}

// TransactionReceipt from ethers uses BigNumber which is not easy to interpret directly from JSON.
// Transform those BigNumbers to string and pass the rest of the data without changes.

const toEthereumTransactionReceipt = (
  receipt: ethers.providers.TransactionReceipt | null
): EthereumTransactionReceipt | null => {
  if (receipt) {
    let effectiveGasPrice = null;
    if (receipt.effectiveGasPrice) {
      effectiveGasPrice = receipt.effectiveGasPrice.toString();
    }
    return {
      ...receipt,
      gasUsed: receipt.gasUsed.toString(),
      cumulativeGasUsed: receipt.cumulativeGasUsed.toString(),
      effectiveGasPrice,
    };
  }

  return null;
};

const toEthereumTransactionResponse = (
  response: ethers.providers.TransactionResponse | null
): EthereumTransactionResponse | null => {
  if (response) {
    let gasPrice = null;
    if (response.gasPrice) {
      gasPrice = response.gasPrice.toString();
    }
    return {
      ...response,
      gasPrice,
      gasLimit: response.gasLimit.toString(),
      value: response.value.toString(),
    };
  }

  return null;
};

export async function poll(
  ethereumish: Ethereumish,
  req: EthereumPollRequest
): Promise<EthereumPollResponse> {
  const initTime = Date.now();
  const currentBlock = await ethereumish.getCurrentBlockNumber();
  const txData = await ethereumish.getTransaction(req.txHash);
  let txBlock, txReceipt, txStatus;
  if (!txData) {
    // tx not found, didn't reach the mempool or it never existed
    txBlock = -1;
    txReceipt = null;
    txStatus = -1;
  } else {
    txReceipt = await ethereumish.getTransactionReceipt(req.txHash);
    if (txReceipt === null) {
      // tx is in the mempool
      txBlock = -1;
      txReceipt = null;
      txStatus = -1;
    } else {
      // tx has been processed
      txBlock = txReceipt.blockNumber;
      txStatus = typeof txReceipt.status === 'number' ? txReceipt.status : -1;
      if (txStatus === 0) {
        const gasUsed = BigNumber.from(txReceipt.gasUsed).toNumber();
        const gasLimit = BigNumber.from(txData.gasLimit).toNumber();
        if (gasUsed / gasLimit > 0.9) {
          throw new HttpException(
            503,
            OUT_OF_GAS_ERROR_MESSAGE,
            OUT_OF_GAS_ERROR_CODE
          );
        }
      }
    }
  }
  return {
    network: ethereumish.chain,
    currentBlock,
    timestamp: initTime,
    txHash: req.txHash,
    txBlock,
    txStatus,
    txData: toEthereumTransactionResponse(txData),
    txReceipt: toEthereumTransactionReceipt(txReceipt),
  };
}

export async function cancel(
  ethereumish: Ethereumish,
  req: EthereumCancelRequest
): Promise<EthereumCancelResponse> {
  const initTime = Date.now();
  let wallet: Wallet;
  try {
    wallet = ethereumish.getWallet(req.privateKey);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }

  // call cancelTx function
  const cancelTx = await ethereumish.cancelTx(wallet, req.nonce);

  return {
    network: ethereumish.chain,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    txHash: cancelTx.hash,
  };
}
