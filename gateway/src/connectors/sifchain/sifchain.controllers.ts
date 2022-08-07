// import Decimal from 'decimal.js-light';
// import { BigNumber } from 'ethers';
import {
  HttpException,
  // LOAD_WALLET_ERROR_CODE,
  // LOAD_WALLET_ERROR_MESSAGE,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
  // TRADE_FAILED_ERROR_CODE,
  // TRADE_FAILED_ERROR_MESSAGE,
  // SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE,
  // SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE,
  // SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_CODE,
  // SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_MESSAGE,
} from '../../services/error-handler';
// import {
//   // latency,
//   // gasCostInEthString,
//   stringWithDecimalToBigNumber,
// } from '../../services/base';
import {
  // Cosmosish,
  ExpectedTrade,
  SifchainishConnector,
  Sifchainish,
  // Uniswapish,
} from '../../services/common-interfaces';
import {
  PriceRequest,
  // PriceResponse,
  // TradeRequest,
  // TradeResponse,
} from '../../amm/amm.requests';

export async function price(
  sifchainish: Sifchainish,
  sifchainishConnector: SifchainishConnector,
  req: PriceRequest
): Promise<any> {
  // const initTime = Date.now();

  const { amount } = req;

  const baseToken = getFullTokenFromSymbol(
    sifchainish,
    sifchainishConnector,
    req.base
  );
  const quoteToken = getFullTokenFromSymbol(
    sifchainish,
    sifchainishConnector,
    req.quote
  );

  const result: ExpectedTrade | string =
    req.side === 'BUY'
      ? await sifchainishConnector.priceSwapOut(
          quoteToken, // tokenIn is quote asset
          baseToken, // tokenOut is base asset
          amount
        )
      : await sifchainishConnector.priceSwapIn(
          baseToken, // tokenIn is base asset
          quoteToken, // tokenOut is quote asset
          amount
        );

  console.log(result);

  // if (typeof result === 'string') {
  //   throw new HttpException(
  //     500,
  //     TRADE_FAILED_ERROR_MESSAGE + result,
  //     TRADE_FAILED_ERROR_CODE
  //   );
  // } else {
  //   const trade = result.trade;
  //   const expectedAmount = result.expectedAmount;

  //   const tradePrice =
  //     req.side === 'BUY' ? trade.executionPrice.invert() : trade.executionPrice;

  //   const gasLimit = sifchainish.gasLimit;
  //   const gasPrice = sifchainish.gasPrice;
  //   return {
  //     network: sifchainish.chain,
  //     timestamp: initTime,
  //     latency: latency(initTime, Date.now()),
  //     base: baseToken.address,
  //     quote: quoteToken.address,
  //     amount: amount.toString(),
  //     expectedAmount: expectedAmount.toSignificant(8),
  //     price: tradePrice.toSignificant(8),
  //     gasPrice: gasPrice,
  //     gasLimit: gasLimit,
  //     gasCost: gasCostInEthString(gasPrice, gasLimit),
  //   };
  // }
}

// export async function trade(
//   ethereumish: Ethereumish,
//   uniswapish: Uniswapish,
//   req: TradeRequest
// ): Promise<TradeResponse> {
//   const initTime = Date.now();

//   const { limitPrice, maxFeePerGas, maxPriorityFeePerGas } = req;

//   let maxFeePerGasBigNumber;
//   if (maxFeePerGas) {
//     maxFeePerGasBigNumber = BigNumber.from(maxFeePerGas);
//   }
//   let maxPriorityFeePerGasBigNumber;
//   if (maxPriorityFeePerGas) {
//     maxPriorityFeePerGasBigNumber = BigNumber.from(maxPriorityFeePerGas);
//   }

//   let wallet: Wallet;
//   try {
//     wallet = await ethereumish.getWallet(req.address);
//   } catch (err) {
//     throw new HttpException(
//       500,
//       LOAD_WALLET_ERROR_MESSAGE + err,
//       LOAD_WALLET_ERROR_CODE
//     );
//   }
//   const amount = getAmount(
//     ethereumish,
//     req.amount,
//     req.side,
//     req.quote,
//     req.base
//   );
//   const baseToken = getFullTokenFromSymbol(ethereumish, uniswapish, req.base);
//   const quoteToken = getFullTokenFromSymbol(ethereumish, uniswapish, req.quote);

//   const result: ExpectedTrade | string =
//     req.side === 'BUY'
//       ? await uniswapish.priceSwapOut(
//           quoteToken, // tokenIn is quote asset
//           baseToken, // tokenOut is base asset
//           amount
//         )
//       : await uniswapish.priceSwapIn(
//           baseToken, // tokenIn is base asset
//           quoteToken, // tokenOut is quote asset
//           amount
//         );

//   if (typeof result === 'string')
//     throw new HttpException(
//       500,
//       TRADE_FAILED_ERROR_MESSAGE + result,
//       TRADE_FAILED_ERROR_CODE
//     );

//   const gasPrice = ethereumish.gasPrice;
//   const gasLimit = uniswapish.gasLimit;

//   if (req.side === 'BUY') {
//     const price = result.trade.executionPrice.invert();
//     if (
//       limitPrice &&
//       new Decimal(price.toFixed(8).toString()).gte(new Decimal(limitPrice))
//     )
//       throw new HttpException(
//         500,
//         SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE(price, limitPrice),
//         SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE
//       );

//     const tx = await uniswapish.executeTrade(
//       wallet,
//       result.trade,
//       gasPrice,
//       uniswapish.router,
//       uniswapish.ttl,
//       uniswapish.routerAbi,
//       uniswapish.gasLimit,
//       req.nonce,
//       maxFeePerGasBigNumber,
//       maxPriorityFeePerGasBigNumber
//     );

//     if (tx.hash) {
//       await ethereumish.txStorage.saveTx(
//         ethereumish.chain,
//         ethereumish.chainId,
//         tx.hash,
//         new Date(),
//         ethereumish.gasPrice
//       );
//     }

//     return {
//       network: ethereumish.chain,
//       timestamp: initTime,
//       latency: latency(initTime, Date.now()),
//       base: baseToken.address,
//       quote: quoteToken.address,
//       amount: amount.toString(),
//       expectedIn: result.expectedAmount.toSignificant(8),
//       price: price.toSignificant(8),
//       gasPrice: gasPrice,
//       gasLimit: gasLimit,
//       gasCost: gasCostInEthString(gasPrice, gasLimit),
//       nonce: tx.nonce,
//       txHash: tx.hash,
//     };
//   } else {
//     const price = result.trade.executionPrice;
//     if (
//       limitPrice &&
//       new Decimal(price.toFixed(8).toString()).gte(new Decimal(limitPrice))
//     )
//       throw new HttpException(
//         500,
//         SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_MESSAGE(price, limitPrice),
//         SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_CODE
//       );

//     const tx = await uniswapish.executeTrade(
//       wallet,
//       result.trade,
//       gasPrice,
//       uniswapish.router,
//       uniswapish.ttl,
//       uniswapish.routerAbi,
//       uniswapish.gasLimit,
//       req.nonce,
//       maxFeePerGasBigNumber,
//       maxPriorityFeePerGasBigNumber
//     );
//     return {
//       network: ethereumish.chain,
//       timestamp: initTime,
//       latency: latency(initTime, Date.now()),
//       base: baseToken.address,
//       quote: quoteToken.address,
//       amount: amount.toString(),
//       expectedOut: result.expectedAmount.toSignificant(8),
//       price: price.toSignificant(8),
//       gasPrice: gasPrice,
//       gasLimit,
//       gasCost: gasCostInEthString(gasPrice, gasLimit),
//       nonce: tx.nonce,
//       txHash: tx.hash,
//     };
//   }
// }

function getFullTokenFromSymbol(
  sifchainish: Sifchainish,
  sifchainishConnector: SifchainishConnector,
  tokenSymbol: string
) {
  console.log(sifchainishConnector);

  const token = sifchainish.getTokenBySymbol(tokenSymbol);

  if (!token)
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + tokenSymbol,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  return token;
}

// function getAmount(
//   cosmosish: Cosmosish,
//   amountAsString: string,
//   side: string,
//   quote: string,
//   base: string
// ) {
//   // the amount is passed in as a string. We must validate the value.
//   // If it is a strictly an integer string, we can pass it interpet it as a BigNumber.
//   // If is a float string, we need to know how many decimal places it has then we can
//   // convert it to a BigNumber.
//   let amount: BigNumber;
//   if (amountAsString.indexOf('.') > -1) {
//     let token;
//     if (side === 'BUY') {
//       token = cosmosish.getTokenBySymbol(quote);
//     } else {
//       token = cosmosish.getTokenBySymbol(base);
//     }
//     if (token) {
//       amount = stringWithDecimalToBigNumber(amountAsString, token.decimals);
//     } else {
//       throw new HttpException(
//         500,
//         TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + token,
//         TOKEN_NOT_SUPPORTED_ERROR_CODE
//       );
//     }
//   } else {
//     amount = BigNumber.from(amountAsString);
//   }
//   return amount;
// }
