import { CronosBaseUniswapishConnectorConfig } from '../cronos-base/cronos-base-uniswapish-connector.config';

export namespace VVSConfig {
  export const config: CronosBaseUniswapishConnectorConfig.NetworkConfig =
    CronosBaseUniswapishConnectorConfig.buildConfig('vvs');
}
