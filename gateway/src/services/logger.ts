import { ConfigManager } from './config-manager';
import winston from 'winston';
import DailyRotateFile from 'winston-daily-rotate-file';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import appRoot from 'app-root-path';
dayjs.extend(utc);

const { LEVEL, MESSAGE } = require('triple-beam');

const errorsWithoutStack = winston.format((erinfo) => {
  if (erinfo instanceof Error) {
    const info = Object.assign({}, erinfo, {
      level: erinfo.level,
      [LEVEL]: erinfo[LEVEL] || erinfo.level,
      message: erinfo.message,
      [MESSAGE]: erinfo[MESSAGE] || erinfo.message,
    });
    return info;
  }
  return erinfo;
});

const errorsWithStack = winston.format((einfo) => {
  if (einfo instanceof Error) {
    const info = Object.assign({}, einfo, {
      level: einfo.level,
      [LEVEL]: einfo[LEVEL] || einfo.level,
      message: einfo.message + `\n\n${einfo.stack}`,
      [MESSAGE]: einfo[MESSAGE] || einfo.message,
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
    return `${localDate} | ${info.level} | ${info.message}`;
  })
);

const sdtoutFormat = winston.format.combine(
  errorsWithoutStack(),
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

export const updateLoggerToStdout = () => {
  ConfigManager.config.LOG_TO_STDOUT === true
    ? logger.add(toStdout)
    : logger.remove(toStdout);
};

updateLoggerToStdout();
