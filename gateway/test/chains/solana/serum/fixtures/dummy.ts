// @ts-nocheck
import { CreateOrdersRequest, OrderSide, OrderType } from "../../../../../src/connectors/serum/serum.types";
import { default as config } from './serumConfig';

// const marketNames = MARKETS.map(item => item.name);
const marketNames = ['SOL/USDT'];

const getRandomChoice = (array: any[]) => array[Math.floor(Math.random() * array.length)];

export const getNewOrderTemplate = (): CreateOrdersRequest => {
  // const side = getRandomChoice(Object.values(OrderSide));
  const side = OrderSide.SELL;
  const price = side == OrderSide.BUY ? 0.1 : 9999.99;
  const amount = side == OrderSide.BUY ? 0.1 : 0.1;
  // const type = getRandomChoice(Object.values(OrderType));
  const type = OrderType.LIMIT;

  return {
    id: Date.now().toString(),
    marketName: getRandomChoice(marketNames),
    ownerAddress: config.solana.wallet.owner.address,
    payerAddress: config.solana.wallet.payer.address,
    side: side,
    price: price,
    amount: amount,
    type: type,
  }
}
