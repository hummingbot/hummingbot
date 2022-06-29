import { Ethereum } from '../chains/ethereum/ethereum';
import { Avalanche } from '../chains/avalanche/avalanche';
import { Harmony } from '../chains/harmony/harmony';
import { Solana, Solanaish } from '../chains/solana/solana';
import { Polygon } from '../chains/polygon/polygon';
import { Uniswap } from '../connectors/uniswap/uniswap';
import { UniswapLP } from '../connectors/uniswap/uniswap.lp';
import { Pangolin } from '../connectors/pangolin/pangolin';
import { Serum } from '../connectors/serum/serum';
import { Ethereumish, Uniswapish, UniswapLPish } from './common-interfaces';
import { Traderjoe } from '../connectors/traderjoe/traderjoe';
import { Sushiswap } from '../connectors/sushiswap/sushiswap';
import { Serumish } from '../connectors/serum/serum';

export type ChainInstance = Ethereumish | Solanaish;

export async function getChain(chain: string, network: string) {
  let chainInstance: ChainInstance;

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

  return chainInstance;
}

type ConnectorType = Uniswapish | UniswapLPish | Serumish;

export async function getConnector(
  chain: string,
  network: string,
  connector: string | undefined
): Promise<ConnectorType> {
  let connectorInstance: ConnectorType;

  if (chain === 'ethereum' && connector === 'uniswap') {
    connectorInstance = Uniswap.getInstance(chain, network);
  } else if (chain === 'ethereum' && connector === 'sushiswap') {
    connectorInstance = Sushiswap.getInstance(chain, network);
  } else if (chain === 'ethereum' && connector === 'uniswapLP') {
    connectorInstance = UniswapLP.getInstance(chain, network);
  } else if (chain === 'avalanche' && connector === 'pangolin') {
    connectorInstance = Pangolin.getInstance(chain, network);
  } else if (chain === 'avalanche' && connector === 'traderjoe') {
    connectorInstance = Traderjoe.getInstance(chain, network);
  } else if (chain === 'solana' && connector === 'serum') {
    connectorInstance = await Serum.getInstance(chain, network);
  } else {
    throw new Error('unsupported chain or connector');
  }

  if (!connectorInstance.ready()) {
    await connectorInstance.init();
  }

  return connectorInstance as ConnectorType;
}
