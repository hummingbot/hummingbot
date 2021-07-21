function RetryOperation(timeouts, options) {
  // Compatibility for the old (timeouts, retryForever) signature
  if (typeof options === 'boolean') {
    options = { forever: options };
  }

  this._originalTimeouts = JSON.parse(JSON.stringify(timeouts));
  this._timeouts = timeouts;
  this._options = options || {};
  this._maxRetryTime = (options && options.maxRetryTime) || Infinity;
  this._fn = null;
  this._errors = [];
  this._attempts = 1;
  this._operationTimeout = null;
  this._operationTimeoutCb = null;
  this._timeout = null;
  this._operationStart = null;

  if (this._options.forever) {
    this._cachedTimeouts = this._timeouts.slice(0);
  }
}
module.exports = RetryOperation;

RetryOperation.prototype.reset = function reset() {
  this._attempts = 1;
  this._timeouts = this._originalTimeouts;
};

RetryOperation.prototype.stop = function stop() {
  if (this._timeout) {
    clearTimeout(this._timeout);
  }

  this._timeouts = [];
  this._cachedTimeouts = null;
};

RetryOperation.prototype.retry = function retry(err) {
  if (this._timeout) {
    clearTimeout(this._timeout);
  }

  if (!err) {
    return false;
  }
  const currentTime = new Date().getTime();
  if (err && currentTime - this._operationStart >= this._maxRetryTime) {
    this._errors.push(err);
    this._errors.unshift(new Error('RetryOperation timeout occurred'));

    return false;
  }

  this._errors.push(err);

  let timeout = this._timeouts.shift();
  if (timeout === undefined) {
    if (this._cachedTimeouts) {
      // retry forever, only keep last error
      this._errors.splice(this._errors.length - 1, this._errors.length);
      this._timeouts = this._cachedTimeouts.slice(0);
      timeout = this._timeouts.shift();
    } else {
      return false;
    }
  }

  const self = this;
  const timer = setTimeout(function tm1() {
    self._attempts++;

    if (self._operationTimeoutCb) {
      self._timeout = setTimeout(function tm2() {
        self._operationTimeoutCb(self._attempts);
      }, self._operationTimeout);

      if (self._options.unref) {
        self._timeout.unref();
      }
    }

    self._fn(self._attempts);
  }, timeout);

  if (this._options.unref) {
    timer.unref();
  }

  return true;
};

RetryOperation.prototype.attempt = function attempt(fn, timeoutOps) {
  this._fn = fn;

  if (timeoutOps) {
    if (timeoutOps.timeout) {
      this._operationTimeout = timeoutOps.timeout;
    }
    if (timeoutOps.cb) {
      this._operationTimeoutCb = timeoutOps.cb;
    }
  }

  const self = this;
  if (this._operationTimeoutCb) {
    this._timeout = setTimeout(function tm() {
      self._operationTimeoutCb();
    }, self._operationTimeout);
  }

  this._operationStart = new Date().getTime();

  this._fn(this._attempts);
};

RetryOperation.prototype.start = RetryOperation.prototype.try;

RetryOperation.prototype.errors = function errorsFn() {
  return this._errors;
};

RetryOperation.prototype.attempts = function attempsFn() {
  return this._attempts;
};

RetryOperation.prototype.mainError = function mainErrorFn() {
  if (this._errors.length === 0) {
    return null;
  }

  const counts = {};
  let mainError = null;
  let mainErrorCount = 0;

  for (let i = 0; i < this._errors.length; i++) {
    const error = this._errors[i];
    const { message } = error;
    const count = (counts[message] || 0) + 1;

    counts[message] = count;

    if (count >= mainErrorCount) {
      mainError = error;
      mainErrorCount = count;
    }
  }

  return mainError;
};
