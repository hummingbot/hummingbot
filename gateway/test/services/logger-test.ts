import { ConfigManagerV2 } from '../../src/services/config-manager-v2';
import { logger, updateLoggerToStdout } from '../../src/services/logger';

describe('Test logger', () => {
  it('updateLoggerToStdout works', (done) => {
    ConfigManagerV2.getInstance().set('logging.logToStdOut', true);
    updateLoggerToStdout();
    expect(logger.transports.entries.length).toBeGreaterThan(0);
    done();
  });
});
