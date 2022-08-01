import {
  // EstimateGasResponse,
  PriceRequest,
  PriceResponse,
  // TradeRequest,
  // TradeResponse,
} from './vault.requests';
// import {
//   price as vaultPrice,
//   trade as vaultTrade,
//   estimateGas as vaultEstimateGas,
// } from '../connectors/cortex/cortex';
import { getChain, getConnector } from '../services/connection-manager';
import {
  // NetworkSelectionRequest,
  Vaultish,
} from '../services/common-interfaces';

export async function price(req: PriceRequest): Promise<PriceResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector: Vaultish = await getConnector<Vaultish>(
    req.chain,
    req.network,
    req.connector
  );
  return connector.price(req.tradeType, req.amount);
}

// export async function trade(req: TradeRequest): Promise<TradeResponse> {
//   const chain = await getChain(req.chain, req.network);
//   const connector: Vaultish = await getConnector<Vaultish>(
//     req.chain,
//     req.network,
//     req.connector
//   );
//   return connector.trade(chain, req);
// }

// export async function estimateGas(
//   req: NetworkSelectionRequest
// ): Promise<EstimateGasResponse> {
//   const chain = await getChain(req.chain, req.network);
//   const connector: Vaultish = <Vaultish>(
//     await getConnector<Vaultish>(req.chain, req.network, req.connector)
//   );
//   return connector.estimateGas(chain, req);
// }
