import { Ethereum } from '../chains/ethereum/ethereum';
import { Avalanche } from '../chains/avalanche/avalanche';
import { Harmony } from '../chains/harmony/harmony';
import { Polygon } from '../chains/polygon/polygon';
import { Uniswap } from '../connectors/uniswap/uniswap';
import { UniswapLP } from '../connectors/uniswap/uniswap.lp';
import { Pangolin } from '../connectors/pangolin/pangolin';
import { Cosmos } from '../chains/cosmos/cosmos';
import { Openocean } from '../connectors/openocean/openocean';
import { Quickswap } from '../connectors/quickswap/quickswap';
import { Perp } from '../connectors/perp/perp';
import { Perpish, Uniswapish, UniswapLPish } from './common-interfaces';
import { Traderjoe } from '../connectors/traderjoe/traderjoe';
import { Sushiswap } from '../connectors/sushiswap/sushiswap';
import { Defikingdoms } from '../connectors/defikingdoms/defikingdoms';

export async function getChain(chain: string, network: string) {
  let chainInstance: any;

  if (chain === 'ethereum') chainInstance = Ethereum.getInstance(network);
  else if (chain === 'avalanche')
    chainInstance = Avalanche.getInstance(network);
  else if (chain === 'polygon') chainInstance = Polygon.getInstance(network);
  else if (chain === 'harmony') chainInstance = Harmony.getInstance(network);
  else if (chain === 'cosmos') chainInstance = Cosmos.getInstance(network);
  else throw new Error('unsupported chain');
  if (!chainInstance.ready()) {
    await chainInstance.init();
  }
  return chainInstance;
}

type ConnectorType<T> = T extends Uniswapish ? Uniswapish : T;

export async function getConnector<T>(
  chain: string,
  network: string,
  connector: string | undefined,
  address?: string
): Promise<ConnectorType<T>> {
  let connectorInstance: Uniswapish | UniswapLPish | Perpish;
  if (
    (chain === 'ethereum' || chain === 'polygon') &&
    connector === 'uniswap'
  ) {
    connectorInstance = Uniswap.getInstance(chain, network);
  } else if (chain === 'polygon' && connector === 'quickswap') {
    connectorInstance = Quickswap.getInstance(chain, network);
  } else if (chain === 'ethereum' && connector === 'sushiswap') {
    connectorInstance = Sushiswap.getInstance(chain, network);
  } else if (
    (chain === 'ethereum' || chain === 'polygon') &&
    connector === 'uniswapLP'
  ) {
    connectorInstance = UniswapLP.getInstance(chain, network);
  } else if (chain === 'ethereum' && connector === 'perp') {
    connectorInstance = Perp.getInstance(chain, network, address);
  } else if (chain === 'avalanche' && connector === 'pangolin') {
    connectorInstance = Pangolin.getInstance(chain, network);
  } else if (chain === 'avalanche' && connector === 'openocean') {
    connectorInstance = Openocean.getInstance(chain, network);
  } else if (chain === 'avalanche' && connector === 'traderjoe') {
    connectorInstance = Traderjoe.getInstance(chain, network);
  } else if (chain === 'harmony' && connector === 'defikingdoms') {
    connectorInstance = Defikingdoms.getInstance(chain, network);
  } else {
    throw new Error('unsupported chain or connector');
  }
  if (!connectorInstance.ready()) {
    await connectorInstance.init();
  }
  return connectorInstance as ConnectorType<T>;
}
