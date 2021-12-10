import winston from 'winston';
import { ConfigManagerV2 } from '../../src/services/config-manager-v2';
import { logger, updateLoggerToStdout } from '../../src/services/logger';

describe('Test logger', () => {
  it('updateLoggerToStdout works', (done) => {
    ConfigManagerV2.getInstance().set('logging.logToStdOut', true);
    updateLoggerToStdout();
    let ofTypeConsole = (element: any) =>
      element instanceof winston.transports.Console;
    expect(logger.transports.some(ofTypeConsole)).toEqual(true);
    ConfigManagerV2.getInstance().set('logging.logToStdOut', false);
    updateLoggerToStdout();
    ofTypeConsole = (element: any) =>
      element instanceof winston.transports.Console;
    expect(logger.transports.some(ofTypeConsole)).toEqual(false);
    done();
  });
});
