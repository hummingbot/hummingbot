import 'jest-extended';
import { ConfigManager } from '../../src/services/config-manager';
import { logger, telemetry } from '../../src/services/logger';

describe('Test telemetry transport works', () => {
  it('test telemetry transport can be added', () => {
    const initTransports = logger.transports.length;
    if (!ConfigManager.config.ENABLE_TELEMETRY) {
      ConfigManager.config.ENABLE_TELEMETRY = true;
      telemetry();
      expect(logger.transports.length).toEqual(initTransports + 1);
    }
  });
});
