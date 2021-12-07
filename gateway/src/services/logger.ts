import { ConfigManager } from './config-manager';
import winston from 'winston';
import DailyRotateFile from 'winston-daily-rotate-file';
import { TelemetryTransport } from './telemetry-transport';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import appRoot from 'app-root-path';
dayjs.extend(utc);

const { LEVEL, MESSAGE } = require('triple-beam');

const errorsWithStack = winston.format((einfo) => {
  if (einfo instanceof Error) {
    const info = Object.assign({}, einfo, {
      level: einfo.level,
      [LEVEL]: einfo[LEVEL] || einfo.level,
      message: einfo.message,
      [MESSAGE]: einfo[MESSAGE] || einfo.message,
      stack: `\n${einfo.stack}` || '',
    });
    return info;
  }
  return einfo;
});

export const getLocalDate = () => {
  const gmtOffset = ConfigManager.config.GMT_OFFSET;
  return dayjs().utcOffset(gmtOffset, false).format('YYYY-MM-DD hh:mm:ss');
};

const logFileFormat = winston.format.combine(
  winston.format.align(),
  errorsWithStack(),
  winston.format.printf((info) => {
    const localDate = getLocalDate();
    return `${localDate} | ${info.level} | ${info.message} | ${info.stack}`;
  })
);

const sdtoutFormat = winston.format.combine(
  winston.format.printf((info) => {
    const localDate = getLocalDate();
    return `${localDate} | ${info.level} | ${info.message}`;
  })
);

const getLogPath = () => {
  let logPath = ConfigManager.config.LOG_PATH;
  logPath = [appRoot.path, 'logs'].join('/');
  return logPath;
};

const allLogsFileTransport = new DailyRotateFile({
  level: 'info',
  filename: `${getLogPath()}/logs_gateway_app.log.%DATE%`,
  datePattern: 'YYYY-MM-DD',
  handleExceptions: true,
  handleRejections: true,
});

export const logger = winston.createLogger({
  level: 'info',
  format: logFileFormat,
  exitOnError: false,
  transports: [allLogsFileTransport],
});

const toStdout = new winston.transports.Console({
  format: sdtoutFormat,
});

const reportingProxy = new TelemetryTransport({
  host: 'https://api.coinalpha.com',
  instanceId: ConfigManager.config.HUMMINGBOT_INSTANCE_ID,
  level: 'http',
});

export const updateLoggerToStdout = () => {
  ConfigManager.config.LOG_TO_STDOUT === true
    ? logger.add(toStdout)
    : logger.remove(toStdout);
};

export const telemetry = () => {
  ConfigManager.config.ENABLE_TELEMETRY === true
    ? logger.add(reportingProxy)
    : logger.remove(reportingProxy);
};

updateLoggerToStdout();
telemetry();
