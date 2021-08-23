import { ConfigManager } from './config-manager';
import winston from 'winston';
import DailyRotateFile from 'winston-daily-rotate-file';
import moment from 'moment';
import appRoot from 'app-root-path';

export const getLocalDate = () => {
  const gmtOffset = ConfigManager.config.GMT_OFFSET;
  let newDate = moment().format('YYYY-MM-DD hh:mm:ss').trim();

  newDate = moment()
    .utcOffset(gmtOffset, false)
    .format('YYYY-MM-DD hh:mm:ss')
    .trim();
  return newDate;
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
  if (ConfigManager.config.LOG_TO_STDOUT == true) {
    logger.add(toStdout);
  } else {
    logger.remove(toStdout);
  }
};

updateLoggerToStdout();
