import { getNotNullOrThrowError } from '../../../../src/connectors/serum/serum.helpers';
import {
  CreateOrdersRequest,
  OrderSide,
  OrderType,
} from '../../../../src/connectors/serum/serum.types';
import { default as config } from './serumConfig';

const marketNames = ['SOL/USDT', 'SOL/USDC'];

const getRandomChoice = (array: any[]) =>
  array[Math.floor(Math.random() * array.length)];

export const getNewOrderTemplate = (configuration?: {
  id?: string;
  marketName?: string;
  ownerAddress?: string;
  payerAddress?: string;
  side?: OrderSide;
  type?: OrderType;
}): CreateOrdersRequest => {
  if (!configuration) configuration = {};
  if (!configuration.id) configuration.id = Date.now().toString();
  if (!configuration.marketName)
    configuration.marketName = getRandomChoice(marketNames);
  if (!configuration.ownerAddress)
    configuration.ownerAddress = config.solana.wallet.owner.publicKey;
  if (!configuration.payerAddress)
    configuration.side == OrderSide.BUY
      ? (configuration.payerAddress = config.solana.wallet.payer.publicKey)
      : (configuration.payerAddress = config.solana.wallet.owner.publicKey);
  if (!configuration.side)
    configuration.side = getRandomChoice(Object.values(OrderSide));
  if (!configuration.type)
    configuration.type = getRandomChoice(Object.values(OrderType));

  const price = configuration.side == OrderSide.BUY ? 0.1 : 9999.99;
  const amount = configuration.side == OrderSide.BUY ? 0.1 : 0.1;

  return {
    id: configuration.id,
    marketName: getNotNullOrThrowError(configuration.marketName),
    ownerAddress: configuration.ownerAddress,
    payerAddress: configuration.payerAddress,
    side: getNotNullOrThrowError(configuration.side),
    price: price,
    amount: amount,
    type: configuration.type,
  };
};

/**
 * Return max of 12 orders for now
 *
 * @param quantity
 */
export const getNewOrdersTemplates = (
  quantity: number
): CreateOrdersRequest[] => {
  let count = 1;
  const result: CreateOrdersRequest[] = [];

  for (const marketName of marketNames) {
    for (const side of Object.values(OrderSide)) {
      for (const type of Object.values(OrderType)) {
        result.push(
          getNewOrderTemplate({
            id: count.toString(),
            marketName: marketName,
            side: side,
            type: type,
          })
        );

        count += 1;

        if (count > quantity) return result;
      }
    }
  }

  return result;
};
