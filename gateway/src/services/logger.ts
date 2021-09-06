import { ConfigManager } from './config-manager';
import winston from 'winston';
import DailyRotateFile from 'winston-daily-rotate-file';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import appRoot from 'app-root-path';
dayjs.extend(utc);

export const getLocalDate = () => {
  const gmtOffset = ConfigManager.config.GMT_OFFSET;
  return dayjs().utcOffset(gmtOffset, false).format('YYYY-MM-DD hh:mm:ss');
};

const logFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.align(),
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
  format: logFormat,
  exitOnError: false,
  transports: [allLogsFileTransport],
});

const toStdout = new winston.transports.Console({
  format: winston.format.simple(),
});

export const updateLoggerToStdout = () => {
  ConfigManager.config.LOG_TO_STDOUT === true
    ? logger.add(toStdout)
    : logger.remove(toStdout);
};

updateLoggerToStdout();
