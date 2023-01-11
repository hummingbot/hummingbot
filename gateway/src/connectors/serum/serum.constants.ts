import { ConfigManagerV2 } from '../../services/config-manager-v2';

const configManager = ConfigManagerV2.getInstance();

export const constants = {
  cache: {
    markets: configManager.get('serum.cache.markets') || 3600, // in seconds
  },
};

export default constants;
