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
} from '../../services/error-handler';
import { Ethereumish } from '../../services/common-interfaces';

import { Curve } from './curve';
import {
  PriceRequest,
  PriceResponse,
  // TradeRequest,
  // TradeResponse,
} from '../../amm/amm.requests';

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

export async function price(
  ethereumish: Ethereumish,
  curve: Curve,
  req: PriceRequest
): Promise<PriceResponse> {
  const initTime = Date.now();

  const amount = getAmount(
    ethereumish,
    req.amount,
    req.side,
    req.quote,
    req.base
  );
  // curve-js takes the tokens as symbols, not addresses
  const baseToken = req.base;
  const quoteToken = req.quote;

  const result: ExpectedTrade | string =
    req.side === 'BUY'
      ? await curve.priceSwapOut(
          quoteToken, // tokenIn is quote asset
          baseToken, // tokenOut is base asset
          amount
        )
      : await curve.priceSwapIn(
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

    const gasLimit = curve.gasLimit;
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
