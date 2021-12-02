import { BigNumber, Wallet } from 'ethers';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
  TRADE_FAILED_ERROR_CODE,
  TRADE_FAILED_ERROR_MESSAGE,
  SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE,
  SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE,
  SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_CODE,
  SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_MESSAGE,
} from '../../../services/error-handler';
import {
  latency,
  gasCostInEthString,
  stringWithDecimalToBigNumber,
} from '../../../services/base';
import {
  UniswapPriceRequest,
  UniswapPriceResponse,
  UniswapTradeRequest,
  UniswapTradeResponse,
  UniswapTradeErrorResponse,
} from './uniswap.requests';
import { Ethereumish } from '../../../services/ethereumish.interface';
import {
  ExpectedTrade,
  Uniswapish,
} from '../../../services/uniswapish.interface';

export async function price(
  ethereumish: Ethereumish,
  uniswapish: Uniswapish,
  req: UniswapPriceRequest
): Promise<UniswapPriceResponse> {
  const initTime = Date.now();

  const amount = getAmount(
    ethereumish,
    req.amount,
    req.side,
    req.quote,
    req.base
  );
  const baseToken = getFullTokenFromSymbol(ethereumish, uniswapish, req.base);
  const quoteToken = getFullTokenFromSymbol(ethereumish, uniswapish, req.quote);

  const result: ExpectedTrade | string =
    req.side === 'BUY'
      ? await uniswapish.priceSwapOut(
          quoteToken, // tokenIn is quote asset
          baseToken, // tokenOut is base asset
          amount
        )
      : await uniswapish.priceSwapIn(
          baseToken, // tokenIn is base asset
          quoteToken, // tokenOut is quote asset
          amount
        );

  if (typeof result === 'string') {
    throw new HttpException(
      500,
      TRADE_FAILED_ERROR_MESSAGE + result,
      TRADE_FAILED_ERROR_CODE
    );
  } else {
    const trade = result.trade;
    const expectedAmount = result.expectedAmount;

    const tradePrice =
      req.side === 'BUY' ? trade.executionPrice.invert() : trade.executionPrice;

    const gasLimit = uniswapish.gasLimit;
    const gasPrice = ethereumish.gasPrice;
    return {
      network: ethereumish.chain,
      timestamp: initTime,
      latency: latency(initTime, Date.now()),
      base: baseToken.address,
      quote: quoteToken.address,
      amount: amount.toString(),
      expectedAmount: expectedAmount.toSignificant(8),
      price: tradePrice.toSignificant(8),
      gasPrice: gasPrice,
      gasLimit: gasLimit,
      gasCost: gasCostInEthString(gasPrice, gasLimit),
    };
  }
}

export async function trade(
  ethereumish: Ethereumish,
  uniswapish: Uniswapish,
  req: UniswapTradeRequest
): Promise<UniswapTradeResponse | UniswapTradeErrorResponse> {
  const initTime = Date.now();

  const { limitPrice, maxFeePerGas, maxPriorityFeePerGas } = req;

  let maxFeePerGasBigNumber;
  if (maxFeePerGas) {
    maxFeePerGasBigNumber = BigNumber.from(maxFeePerGas);
  }
  let maxPriorityFeePerGasBigNumber;
  if (maxPriorityFeePerGas) {
    maxPriorityFeePerGasBigNumber = BigNumber.from(maxPriorityFeePerGas);
  }

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
  const amount = getAmount(
    ethereumish,
    req.amount,
    req.side,
    req.quote,
    req.base
  );
  const baseToken = getFullTokenFromSymbol(ethereumish, uniswapish, req.base);
  const quoteToken = getFullTokenFromSymbol(ethereumish, uniswapish, req.quote);

  const result: ExpectedTrade | string =
    req.side === 'BUY'
      ? await uniswapish.priceSwapOut(
          quoteToken, // tokenIn is quote asset
          baseToken, // tokenOut is base asset
          amount
        )
      : await uniswapish.priceSwapIn(
          baseToken, // tokenIn is base asset
          quoteToken, // tokenOut is quote asset
          amount
        );

  if (typeof result === 'string')
    throw new HttpException(
      500,
      TRADE_FAILED_ERROR_MESSAGE + result,
      TRADE_FAILED_ERROR_CODE
    );

  const gasPrice = ethereumish.gasPrice;
  const gasLimit = uniswapish.gasLimit;

  if (req.side === 'BUY') {
    const price = result.trade.executionPrice.invert();
    if (
      limitPrice &&
      BigNumber.from(price.toFixed(8)).gte(BigNumber.from(limitPrice))
    )
      throw new HttpException(
        500,
        SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE(price, limitPrice),
        SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE
      );

    const tx = await uniswapish.executeTrade(
      wallet,
      result.trade,
      gasPrice,
      uniswapish.router,
      uniswapish.ttl,
      uniswapish.routerAbi,
      uniswapish.gasLimit,
      req.nonce,
      maxFeePerGasBigNumber,
      maxPriorityFeePerGasBigNumber
    );

    return {
      network: ethereumish.chain,
      timestamp: initTime,
      latency: latency(initTime, Date.now()),
      base: baseToken.address,
      quote: quoteToken.address,
      amount: amount.toString(),
      expectedIn: result.expectedAmount.toSignificant(8),
      price: price.toSignificant(8),
      gasPrice: gasPrice,
      gasLimit: gasLimit,
      gasCost: gasCostInEthString(gasPrice, gasLimit),
      nonce: tx.nonce,
      txHash: tx.hash,
    };
  } else {
    const price = result.trade.executionPrice;
    if (
      limitPrice &&
      BigNumber.from(price.toFixed(8)).gte(BigNumber.from(limitPrice))
    )
      throw new HttpException(
        500,
        SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_MESSAGE(price, limitPrice),
        SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_CODE
      );

    const tx = await uniswapish.executeTrade(
      wallet,
      result.trade,
      gasPrice,
      uniswapish.router,
      uniswapish.ttl,
      uniswapish.routerAbi,
      uniswapish.gasLimit,
      req.nonce,
      maxFeePerGasBigNumber,
      maxPriorityFeePerGasBigNumber
    );
    return {
      network: ethereumish.chain,
      timestamp: initTime,
      latency: latency(initTime, Date.now()),
      base: baseToken.address,
      quote: quoteToken.address,
      amount: amount.toString(),
      expectedOut: result.expectedAmount.toSignificant(8),
      price: price.toSignificant(8),
      gasPrice: gasPrice,
      gasLimit,
      gasCost: gasCostInEthString(gasPrice, gasLimit),
      nonce: tx.nonce,
      txHash: tx.hash,
    };
  }
}

function getFullTokenFromSymbol(
  ethereumish: Ethereumish,
  uniswapish: Uniswapish,
  tokenSymbol: string
) {
  const token = ethereumish.getTokenBySymbol(tokenSymbol);
  let fullToken;
  if (token) {
    fullToken = uniswapish.getTokenByAddress(token.address);
  }
  if (!fullToken)
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + tokenSymbol,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  return fullToken;
}

function getAmount(
  ethereumish: Ethereumish,
  amountAsString: string,
  side: string,
  quote: string,
  base: string
) {
  // the amount is passed in as a string. We must validate the value.
  // If it is a strictly an integer string, we can pass it interpet it as a BigNumber.
  // If is a float string, we need to know how many decimal places it has then we can
  // convert it to a BigNumber.
  let amount: BigNumber;
  if (amountAsString.indexOf('.') > -1) {
    let token;
    if (side === 'BUY') {
      token = ethereumish.getTokenBySymbol(quote);
    } else {
      token = ethereumish.getTokenBySymbol(base);
    }
    if (token) {
      amount = stringWithDecimalToBigNumber(amountAsString, token.decimals);
    } else {
      throw new HttpException(
        500,
        TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + token,
        TOKEN_NOT_SUPPORTED_ERROR_CODE
      );
    }
  } else {
    amount = BigNumber.from(amountAsString);
  }
  return amount;
}
