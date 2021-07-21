function noop(){}

export default global.console ? global.console : {
  log: noop,
  info: noop,
  warn: noop,
  error: noop,
  dir: noop,
  assert: noop,
  time: noop,
  timeEnd: noop,
  trace: noop
};
