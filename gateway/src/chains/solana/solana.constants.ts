import { ConfigManagerV2 } from '../../services/config-manager-v2';

const configManager = ConfigManagerV2.getInstance();

export const constants = {
  retry: {
    all: {
      maxNumberOfRetries:
        configManager.get('solana.retry.all.maxNumberOfRetries') || 0, // 0 means no retries
      delayBetweenRetries:
        configManager.get('solana.retry.all.delayBetweenRetries') || 0, // 0 means no delay (milliseconds)
    },
  },
  timeout: {
    all: configManager.get('solana.timeout.all') || 0, // 0 means no timeout (milliseconds)
  },
  parallel: {
    all: {
      batchSize: configManager.get('solana.parallel.all.batchSize') || 0, // 0 means no batching (group all)
      delayBetweenBatches:
        configManager.get('solana.parallel.all.delayBetweenBatches') || 0, // 0 means no delay (milliseconds)
    },
  },
};

export default constants;
