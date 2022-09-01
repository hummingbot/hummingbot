import { Ethereum } from '../chains/ethereum/ethereum';
import { Avalanche } from '../chains/avalanche/avalanche';
import { Harmony } from '../chains/harmony/harmony';
import { Solana, Solanaish } from '../chains/solana/solana';
import { Polygon } from '../chains/polygon/polygon';
import { Uniswap } from '../connectors/uniswap/uniswap';
import { UniswapLP } from '../connectors/uniswap/uniswap.lp';
import { Pangolin } from '../connectors/pangolin/pangolin';
import { Openocean } from '../connectors/openocean/openocean';
import { Serum } from '../connectors/serum/serum';
import { Quickswap } from '../connectors/quickswap/quickswap';
import { Perp } from '../connectors/perp/perp';
import {
  Ethereumish,
  Perpish,
  Uniswapish,
  UniswapLPish,
} from './common-interfaces';
import { Traderjoe } from '../connectors/traderjoe/traderjoe';
import { Sushiswap } from '../connectors/sushiswap/sushiswap';
import { Defikingdoms } from '../connectors/defikingdoms/defikingdoms';
import { Defira } from '../connectors/defira/defira';
import { Serumish } from '../connectors/serum/serum';

export type ChainUnion = Ethereumish | Solanaish;

export type Chain<T> = T extends Ethereumish
  ? Ethereumish
  : T extends Solanaish
  ? Solanaish
  : never;

export async function getChain<T>(
  chain: string,
  network: string
): Promise<Chain<T>> {
  let chainInstance: ChainUnion;

  if (chain === 'ethereum') chainInstance = Ethereum.getInstance(network);
  else if (chain === 'avalanche')
    chainInstance = Avalanche.getInstance(network);
  else if (chain === 'polygon') chainInstance = Polygon.getInstance(network);
  else if (chain === 'harmony') chainInstance = Harmony.getInstance(network);
  else if (chain === 'solana')
    chainInstance = await Solana.getInstance(network);
  else throw new Error('unsupported chain');

  if (!chainInstance.ready()) {
    await chainInstance.init();
  }

  return chainInstance as Chain<T>;
}

type ConnectorUnion = Uniswapish | UniswapLPish | Perpish | Serumish;

export type Connector<T> = T extends Uniswapish
  ? Uniswapish
  : T extends UniswapLPish
  ? UniswapLPish
  : T extends Perpish
  ? Perpish
  : T extends Serumish
  ? Serumish
  : never;

export async function getConnector<T>(
  chain: string,
  network: string,
  connector: string | undefined,
  address?: string
): Promise<Connector<T>> {
  let connectorInstance: ConnectorUnion;

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
  } else if (chain === 'harmony' && connector === 'defira') {
    connectorInstance = Defira.getInstance(chain, network);
  } else if (chain === 'solana' && connector === 'serum') {
    connectorInstance = await Serum.getInstance(chain, network);
  } else {
    throw new Error('unsupported chain or connector');
  }

  if (!connectorInstance.ready()) {
    await connectorInstance.init();
  }

  return connectorInstance as Connector<T>;
}
