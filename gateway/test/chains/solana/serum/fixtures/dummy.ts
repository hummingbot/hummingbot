import {CreateOrdersRequest, OrderSide, OrderType} from "../../../../../src/connectors/serum/serum.types";
import {default as config} from './serumConfig';
// @ts-ignore
import {MARKETS} from "@project-serum/serum";

// const marketNames = MARKETS.map(item => item.name);
const marketNames = ['BTC/USDT', 'ETH/USDT'];

const getRandomChoice = (array: any[]) => array[Math.floor(Math.random() * array.length)];

export const getNewOrderTemplate = (): CreateOrdersRequest => {
  return {
    marketName: getRandomChoice(marketNames),
    ownerAddress: config.solana.wallet.owner.address,
    payerAddress: config.solana.wallet.payer.address,
    side: getRandomChoice(Object.values(OrderSide)),
    price: Math.random(),
    amount: 10*(1 + Math.random()),
    type: getRandomChoice(Object.values(OrderType)),
  }
}
