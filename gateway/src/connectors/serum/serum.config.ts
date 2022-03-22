import { ConfigManagerV2 } from '../../services/config-manager-v2';

export namespace SerumConfig {
  export interface Config {
    allowedSlippage: string;
    ttl: number;
  }

  export const config: Config = {
    allowedSlippage: ConfigManagerV2.getInstance().get('serum.allowedSlippage'),
    ttl: ConfigManagerV2.getInstance().get('serum.ttl'),
  };
}
