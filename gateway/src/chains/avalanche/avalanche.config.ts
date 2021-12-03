import { Config, getEthereumConfig } from '../ethereum/ethereum.config';

export namespace AvalancheConfig {
  export const config: Config = getEthereumConfig('avalanche');
}
