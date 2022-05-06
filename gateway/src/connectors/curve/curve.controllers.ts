import {
  HttpException,
  TRADE_FAILED_ERROR_CODE,
  TRADE_FAILED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { latency } from '../../services/base';
import { Ethereumish } from '../../services/common-interfaces';
import { Curve } from './curve';
import {
  PriceRequest,
  PriceResponse,
  // TradeRequest,
  // TradeResponse,
} from '../../amm/amm.requests';

export async function price(
  ethereumish: Ethereumish,
  curve: Curve,
  req: PriceRequest
): Promise<PriceResponse> {
  const initTime = Date.now();

  // curve-js takes the tokens as symbols, not addresses
  const baseToken = req.base;
  const quoteToken = req.quote;

  const result: any =
    req.side === 'BUY'
      ? curve.price(quoteToken, baseToken, req.amount)
      : curve.price(baseToken, quoteToken, req.amount);

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
      base: '', // baseToken.address,
      quote: '', // quoteToken.address,
      amount: result.amount, // amount.toString(),
      expectedAmount: expectedAmount.toSignificant(8),
      price: tradePrice.toSignificant(8),
      gasPrice: gasPrice,
      gasLimit: gasLimit,
      gasCost: '0', // gasCostInEthString(gasPrice, gasLimit),
      rawAmount: '0',
      gasPriceToken: 'ETH',
    };
  }
}
