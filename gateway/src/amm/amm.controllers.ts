import {
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
} from './amm.requests';
import { Ethereum } from '../chains/ethereum/ethereum';
import { Avalanche } from '../chains/avalanche/avalanche';
import { Uniswap } from '../connectors/uniswap/uniswap';
import { Pangolin } from '../connectors/pangolin/pangolin';
import {
  price as uniswapPrice,
  trade as uniswapTrade,
} from '../connectors/uniswap/uniswap.controllers';
import { Ethereumish } from '../services/common-interfaces';

export async function getChain(
  chain: string,
  network: string
): Promise<Ethereumish> {
  let chainInstance: Ethereumish;
  if (chain === 'ethereum') chainInstance = Ethereum.getInstance(network);
  else if (chain === 'avalanche')
    chainInstance = Avalanche.getInstance(network);
  else throw new Error('unsupported chain');
  if (!chainInstance.ready()) {
    await chainInstance.init();
  }
  return chainInstance;
}

export async function getConnector(
  chain: string,
  network: string,
  connector: string
) {
  let connectorInstance: any;
  if (chain === 'ethereum' && connector === 'uniswap')
    connectorInstance = Uniswap.getInstance(chain, network);
  else if (chain === 'avalanche' && connector === 'pangolin')
    connectorInstance = Pangolin.getInstance(chain, network);
  else throw new Error('unsupported chain or connector');
  if (!connectorInstance.ready()) {
    await connectorInstance.init();
  }
  return connectorInstance;
}

export async function price(req: PriceRequest): Promise<PriceResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  return uniswapPrice(chain, connector, req);
}

export async function trade(req: TradeRequest): Promise<TradeResponse> {
  const chain = await getChain(req.chain, req.network);
  const connector = await getConnector(req.chain, req.network, req.connector);
  return uniswapTrade(chain, connector, req);
}
