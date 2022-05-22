import { ConfigManagerV2 } from '../../services/config-manager-v2';
export namespace CurveConfig {
  export interface NetworkConfig {
    allowedSlippage: string;
  }

  export const config: NetworkConfig = {
    allowedSlippage: ConfigManagerV2.getInstance().get(`curve.allowedSlippage`),
  };
}
