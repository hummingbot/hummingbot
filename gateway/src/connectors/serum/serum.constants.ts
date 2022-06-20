import { ConfigManagerV2 } from '../../services/config-manager-v2';

const configManager = ConfigManagerV2.getInstance();

export const constants = {
  parallel: {
    all: {
      batchSize: configManager.get('serum.parallel.all.batchSize') || 10,
      // in milliseconds
      delayBetweenBatches:
        configManager.get('serum.parallel.all.delayBetweenBatches') || 15000,
    },
  },
  cache: {
    // in seconds
    markets: configManager.get('serum.cache.markets') || 3600,
  },
};

export default constants;
