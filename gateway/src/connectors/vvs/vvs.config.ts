import { CronosBaseUniswapishConnectorConfig } from '../cronos-base/cronos-base-uniswapish-connector.config';

export namespace VVSConfig {
  const tradingTypes = ['EVM_AMM'];
  export const config: CronosBaseUniswapishConnectorConfig.NetworkConfig =
    CronosBaseUniswapishConnectorConfig.buildConfig('vvs', tradingTypes);
}
