import { CronosBaseConnectorConfig } from '../cronos-base/cronos-base-connector.config';

export namespace MadMeerkatConfig {
  export const config: CronosBaseConnectorConfig.NetworkConfig =
    CronosBaseConnectorConfig.buildConfig('mad_meerkat');
}
