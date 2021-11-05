import { BigNumber } from 'ethers';
import { stringWithDecimalToBigNumber } from '../../../services/base';
import { EthereumBase } from '../../../services/ethereum-base';
import { Pangolin } from './pangolin';

// the amount is passed in as a string. We must validate the value.
// If it is a strictly an integer string, we can pass it interpet it as a BigNumber.
// If is a float string, we need to know how many decimal places it has then we can
// convert it to a BigNumber.
export function getAmountInBigNumber(
  ethereumBase: EthereumBase,
  amount: string,
  side: string,
  quote: string,
  base: string
): BigNumber {
  let amountInBigNumber: BigNumber;
  if (amount.indexOf('.') > -1) {
    let token;
    if (side === 'BUY') {
      token = ethereumBase.getTokenBySymbol(quote);
    } else {
      token = ethereumBase.getTokenBySymbol(base);
    }
    if (token) {
      amountInBigNumber = stringWithDecimalToBigNumber(amount, token.decimals);
    } else {
      throw new Error('Unrecognized token symbol for amount.');
    }
  } else {
    amountInBigNumber = BigNumber.from(amount);
  }
  return amountInBigNumber;
}

export async function getTrade(
  pangolin: Pangolin,
  side: string,
  quoteTokenAddress: string,
  baseTokenAddress: string,
  amount: BigNumber
) {
  const result =
    side === 'BUY'
      ? await pangolin.priceSwapOut(
          quoteTokenAddress, // tokenIn is quote asset
          baseTokenAddress, // tokenOut is base asset
          amount
        )
      : await pangolin.priceSwapIn(
          baseTokenAddress, // tokenIn is base asset
          quoteTokenAddress, // tokenOut is quote asset
          amount
        );

  if (typeof result === 'string')
    throw new Error('Uniswap trade query failed: ' + result);

  return {
    trade: result.trade,
    expectedAmount: result.expectedAmount,
    tradePrice:
      side === 'BUY'
        ? result.trade.executionPrice.invert()
        : result.trade.executionPrice,
  };
}
