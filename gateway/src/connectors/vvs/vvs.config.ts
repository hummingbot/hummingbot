import { CronosBaseConnectorConfig } from '../cronos-base/cronos-base-connector.config';

export namespace VVSConfig {
  export const config: CronosBaseConnectorConfig.NetworkConfig =
    CronosBaseConnectorConfig.buildConfig('vvs');
}
