import TransportStream from 'winston-transport';
import 'jest-extended';
import { ConfigManager } from '../../src/services/config-manager';
import { logger, telemetry } from '../../src/services/logger';
import { patch, unpatch } from './patch';

export interface NewHttpStream extends TransportStream {
  sendLogs(): void;
  _request(options: any, callback: any): void;
}

beforeAll(() => {
  if (!ConfigManager.config.ENABLE_TELEMETRY) {
    ConfigManager.config.ENABLE_TELEMETRY = true;
    telemetry();
  }

  const fileLogs = logger.transports.find((transport) => {
    return transport.level === 'info';
  }) as TransportStream;

  const consoleLog = logger.transports.find((transport) => {
    return transport.level === undefined;
  }) as TransportStream;

  logger.remove(fileLogs);
  logger.remove(consoleLog);
});

afterEach(() => unpatch());

const streamReturn = {
  level: 'http',
  message: ['1636116532749 - \tTest tele.'],
};

const patchStream = () => {
  patch(logger, 'stream', () => {
    return streamReturn;
  });
};

const patchRequest = () => {
  const tele = logger.transports[0] as NewHttpStream;
  patch(tele, '_request', () => {
    return streamReturn;
  });
};

describe('Test telemetry transport functionality', () => {
  it('test logging by patching stream', () => {
    patchRequest();
    patchStream();
    const tele = logger.transports[0] as NewHttpStream;

    logger.http('Test tele stream.');
    tele.sendLogs();
  });
});
