import {SerumMarketsRequest, SerumMarketsResponse, SerumOrderbookRequest} from './serum.requests';
import {Solanaish} from "../../chains/solana/solana";
import {Serumish} from "./serum";

export async function markets(
  solana: Solanaish,
  serum: Serumish,
  req: SerumMarketsRequest
): Promise<SerumMarketsResponse> {
  // TODO implement!!!
  console.log(solana, serum, req);
}

export async function orderbook(
  solana: Solanaish,
  serum: Serumish,
  req: SerumOrderbookRequest
) {
  console.log(body);
  return body;
}

export async function getOrders(req: any) {
  console.log(body);
  return body;
}

export async function postOrder(req: any) {
  console.log(body);
  return body;
}

export async function deleteOrders(req: any) {
  console.log(body);
  return body;
}

export async function fills(req: any) {
  console.log(body);
  return body;
}
