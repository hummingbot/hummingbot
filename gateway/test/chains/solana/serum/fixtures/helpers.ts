import { PublicKey } from '@solana/web3.js';
import BN from 'bn.js';
import { convertOrderSideToSerumSide } from '../../../../../src/connectors/serum/serum.convertors';
import {
  getNotNullOrThrowError,
  getRandonBN,
} from '../../../../../src/connectors/serum/serum.helpers';
import {
  CreateOrderResponse,
  CreateOrdersRequest,
  OrderBook,
  OrderSide,
  OrderStatus,
  OrderType,
  SerumOpenOrders,
  SerumOrder,
} from '../../../../../src/connectors/serum/serum.types';
import { default as config } from './config';
import { randomUUID } from 'crypto';

export interface CreateOrderData {
  request: CreateOrdersRequest;
  response: CreateOrderResponse;
}

const marketNames = ['SOL/USDT', 'SOL/USDC'];

const getRandomChoice = (array: any[]) =>
  array[Math.floor(Math.random() * array.length)];

export const getNewCandidateOrderTemplate = (configuration?: {
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
    if (configuration.side == OrderSide.SELL) {
      configuration.payerAddress = config.solana.wallet.owner.publicKey;
    } else {
      if (configuration.marketName == 'SOL/USDT') {
        configuration.payerAddress =
          config.solana.wallet.payer['SOL/USDT'].publicKey;
      } else if (configuration.marketName == 'SOL/USDC') {
        configuration.payerAddress =
          config.solana.wallet.payer['SOL/USDC'].publicKey;
      } else {
        throw new Error('Unrecognized market name.');
      }
    }
  if (!configuration.side)
    configuration.side = getRandomChoice(Object.values(OrderSide));
  if (!configuration.type)
    configuration.type = getRandomChoice([OrderType.LIMIT]);

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
export const getNewCandidateOrdersTemplates = (
  quantity: number,
  initialId: number = 1
): CreateOrdersRequest[] => {
  let count = initialId;
  const result: CreateOrdersRequest[] = [];

  while (count <= quantity) {
    for (const marketName of marketNames) {
      for (const side of Object.values(OrderSide)) {
        for (const type of [OrderType.LIMIT]) {
          result.push(
            getNewCandidateOrderTemplate({
              id: count.toString(),
              marketName,
              side,
              type,
            })
          );

          count = count + 1;

          if (count > quantity) return result;
        }
      }
    }
  }

  return result;
};

export const getOrderPairsFromCandidateOrders = (
  orderCandidates: CreateOrdersRequest[]
): CreateOrderData[] => {
  return orderCandidates.map((request) => {
    return {
      request: request,
      response: {
        ...request,
        exchangeId: randomUUID(),
        fee: 0.01,
        status: OrderStatus.OPEN,
        signature: randomUUID(),
      },
    };
  });
};

export const getNewSerumOrders = (
  candidateOrders: CreateOrdersRequest[]
): SerumOrder[] => {
  const result = [];

  for (const candidateOrder of candidateOrders) {
    result.push({
      orderId:
        (candidateOrder as unknown as CreateOrderResponse).exchangeId ||
        getRandonBN(),
      openOrdersAddress: new PublicKey(
        'DaosjpvtAxwL6GFDSL31o9pU5somKjifbkt32bEgLddf'
      ),
      openOrdersSlot: Math.random(),
      price: candidateOrder.price,
      priceLots: getRandonBN(),
      size: candidateOrder.amount,
      feeTier: Math.random(),
      sizeLots: getRandonBN(),
      side: convertOrderSideToSerumSide(candidateOrder.side),
      clientId: new BN(getNotNullOrThrowError(candidateOrder.id)),
    } as SerumOrder);
  }

  return result;
};

export const changeAndConvertToSerumOpenOrder = (
  index: number,
  orderBook: OrderBook,
  candidateOrder: CreateOrdersRequest
): SerumOpenOrders => {
  const orderBookOrder: SerumOrder = Array.from(orderBook.orderBook.asks)[
    index
  ];

  const serumOpenOrder = new SerumOpenOrders(
    orderBookOrder.openOrdersAddress,
    undefined,
    orderBook.market.programId
  );

  serumOpenOrder.clientIds = [
    new BN(getNotNullOrThrowError(candidateOrder.id)),
  ];

  orderBookOrder.clientId = new BN(getNotNullOrThrowError(candidateOrder.id));

  return serumOpenOrder;
};

export const convertToSerumOpenOrders = (
  startIndex: number,
  orderBook: OrderBook,
  candidateOrders: CreateOrdersRequest[]
): SerumOpenOrders[] => {
  const result = [];

  let count = startIndex;
  for (const candidateOrder of candidateOrders) {
    result.push(
      changeAndConvertToSerumOpenOrder(count, orderBook, candidateOrder)
    );

    count++;
  }

  return result;
};
