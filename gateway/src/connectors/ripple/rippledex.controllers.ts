import { StatusCodes } from 'http-status-codes';
import { Rippleish } from '../../chains/ripple/ripple';
import { ResponseWrapper } from '../../services/common-interfaces';
// import { HttpException } from '../../services/error-handler';
import { RippleDEXish } from './rippledex';

/**
 * Get the mid price of a token pair
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getTickers(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.getTicker(request.base, request.quote);

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Get the order book of a token pair
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getOrderBooks(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.getOrderBooks(
    request.base,
    request.quote,
    request.limit
  );

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Get the detail on the created order
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getOrders(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.getOrders(request.tx);

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Create an order on order book
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function createOrders(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.createOrders(
    request.address,
    request.base,
    request.quote,
    request.side,
    request.price,
    request.amount
  );

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Cancel an order on order book
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function cancelOrders(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.cancelOrders(
    request.address,
    request.offerSequence
  );

  response.status = StatusCodes.OK;

  return response;
}

/**
 * Get the order book of a token pair
 *
 * @param _ripple
 * @param rippledex
 * @param request
 */
export async function getOpenOrders(
  _ripple: Rippleish,
  rippledex: RippleDEXish,
  request: any
): Promise<ResponseWrapper<any>> {
  const response = new ResponseWrapper<any>();

  response.body = await rippledex.getOpenOrders(request.address);

  response.status = StatusCodes.OK;

  return response;
}