// @ts-nocheck
import {CreateOrdersRequest, OrderSide, OrderType} from "../../../../../src/connectors/serum/serum.types";
import {default as config} from './serumConfig';
import {MARKETS} from "@project-serum/serum";

// const marketNames = MARKETS.map(item => item.name);
const marketNames = ['SOL/USDT'];

const getRandomChoice = (array: any[]) => array[Math.floor(Math.random() * array.length)];

export const getNewOrderTemplate = (): CreateOrdersRequest => {
  // const side = getRandomChoice(Object.values(OrderSide));
  const side = OrderSide.SELL;
  const price = side == OrderSide.BUY ? 0.1 : 9999;
  const amount = side == OrderSide.BUY ? 0.1 : 0.5;
  // const type = getRandomChoice(Object.values(OrderType));
  const type = OrderType.LIMIT;

  return {
    marketName: getRandomChoice(marketNames),
    ownerAddress: config.solana.wallet.owner.address,
    payerAddress: config.solana.wallet.payer.address,
    side: side,
    price: price,
    amount: amount,
    type: type,
  }
}
