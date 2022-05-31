import { Ethereum } from '../chains/ethereum/ethereum';
import { Avalanche } from '../chains/avalanche/avalanche';
import { Harmony } from '../chains/harmony/harmony';
import { Curve } from '../connectors/curve/curve';
import { Uniswap } from '../connectors/uniswap/uniswap';
import { Pangolin } from '../connectors/pangolin/pangolin';
import { Ethereumish, Uniswapish } from './common-interfaces';
import { Traderjoe } from '../connectors/traderjoe/traderjoe';

export async function getChain(
  chain: string,
  network: string
): Promise<Ethereumish> {
  let chainInstance: Ethereumish;
  if (chain === 'ethereum') chainInstance = Ethereum.getInstance(network);
  else if (chain === 'avalanche')
    chainInstance = Avalanche.getInstance(network);
  else if (chain === 'harmony') chainInstance = Harmony.getInstance(network);
  else throw new Error('unsupported chain');
  if (!chainInstance.ready) {
    await chainInstance.init();
  }
  return chainInstance;
}

export async function getConnector(
  chain: string,
  network: string,
  connector: string | undefined
): Promise<Uniswapish | Curve> {
  let connectorInstance: any;
  if (chain === 'ethereum' && connector === 'uniswap')
    connectorInstance = Uniswap.getInstance(chain, network);
  else if (chain === 'ethereum' && connector === 'curve')
    connectorInstance = Curve.getInstance(chain, network);
  else if (chain === 'avalanche' && connector === 'pangolin')
    connectorInstance = Pangolin.getInstance(chain, network);
  else if (chain === 'avalanche' && connector === 'traderjoe')
    connectorInstance = Traderjoe.getInstance(chain, network);
  else throw new Error('unsupported chain or connector');
  if (!connectorInstance.ready) {
    await connectorInstance.init();
  }
  return connectorInstance;
}
