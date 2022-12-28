import { CronosBaseUniswapishConnectorConfig } from '../cronos-base/cronos-base-uniswapish-connector.config';

export namespace MadMeerkatConfig {
  const tradingTypes = ['EVM_AMM'];
  export const config: CronosBaseUniswapishConnectorConfig.NetworkConfig =
    CronosBaseUniswapishConnectorConfig.buildConfig(
      'mad_meerkat',
      tradingTypes
    );
}
