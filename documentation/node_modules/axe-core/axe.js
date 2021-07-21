/*! axe v3.5.5
 * Copyright (c) 2020 Deque Systems, Inc.
 *
 * Your use of this Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 * This entire copyright notice must appear in every copy of this file you
 * distribute or in any file that contains substantial portions of this source
 * code.
 */
(function axeFunction(window) {
  var global = window;
  var document = window.document;
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  var axe = axe || {};
  axe.version = '3.5.5';
  if (typeof define === 'function' && define.amd) {
    define('axe-core', [], function() {
      'use strict';
      return axe;
    });
  }
  if ((typeof module === 'undefined' ? 'undefined' : _typeof(module)) === 'object' && module.exports && typeof axeFunction.toString === 'function') {
    axe.source = '(' + axeFunction.toString() + ')(typeof window === "object" ? window : this);';
    module.exports = axe;
  }
  if (typeof window.getComputedStyle === 'function') {
    window.axe = axe;
  }
  var commons;
  function SupportError(error) {
    this.name = 'SupportError';
    this.cause = error.cause;
    this.message = '`'.concat(error.cause, '` - feature unsupported in your environment.');
    if (error.ruleId) {
      this.ruleId = error.ruleId;
      this.message += ' Skipping '.concat(this.ruleId, ' rule.');
    }
    this.stack = new Error().stack;
  }
  SupportError.prototype = Object.create(Error.prototype);
  SupportError.prototype.constructor = SupportError;
  (function() {
    function r(e, n, t) {
      function o(i, f) {
        if (!n[i]) {
          if (!e[i]) {
            var c = 'function' == typeof require && require;
            if (!f && c) {
              return c(i, !0);
            }
            if (u) {
              return u(i, !0);
            }
            var a = new Error('Cannot find module \'' + i + '\'');
            throw a.code = 'MODULE_NOT_FOUND', a;
          }
          var p = n[i] = {
            exports: {}
          };
          e[i][0].call(p.exports, function(r) {
            var n = e[i][1][r];
            return o(n || r);
          }, p, p.exports, r, e, n, t);
        }
        return n[i].exports;
      }
      for (var u = 'function' == typeof require && require, i = 0; i < t.length; i++) {
        o(t[i]);
      }
      return o;
    }
    return r;
  })()({
    1: [ function(_dereq_, module, exports) {
      if (!('Promise' in window)) {
        _dereq_('es6-promise').polyfill();
      }
      if (!('Uint32Array' in window)) {
        _dereq_('core-js/features/typed-array/uint32-array');
      }
      if (window.Uint32Array) {
        if (!('some' in window.Uint32Array.prototype)) {
          _dereq_('core-js/features/typed-array/some');
        }
        if (!('reduce' in window.Uint32Array.prototype)) {
          _dereq_('core-js/features/typed-array/reduce');
        }
      }
      _dereq_('weakmap-polyfill');
      axe.imports = {
        axios: _dereq_('axios'),
        CssSelectorParser: _dereq_('css-selector-parser').CssSelectorParser,
        doT: _dereq_('@deque/dot'),
        emojiRegexText: _dereq_('emoji-regex'),
        memoize: _dereq_('memoizee')
      };
    }, {
      '@deque/dot': 2,
      axios: 3,
      'core-js/features/typed-array/reduce': 31,
      'core-js/features/typed-array/some': 32,
      'core-js/features/typed-array/uint32-array': 33,
      'css-selector-parser': 155,
      'emoji-regex': 158,
      'es6-promise': 202,
      memoizee: 223,
      'weakmap-polyfill': 245
    } ],
    2: [ function(_dereq_, module, exports) {
      (function(global) {
        (function() {
          'use strict';
          var doT = {
            name: 'doT',
            version: '1.1.1',
            templateSettings: {
              evaluate: /\{\{([\s\S]+?(\}?)+)\}\}/g,
              interpolate: /\{\{=([\s\S]+?)\}\}/g,
              encode: /\{\{!([\s\S]+?)\}\}/g,
              use: /\{\{#([\s\S]+?)\}\}/g,
              useParams: /(^|[^\w$])def(?:\.|\[[\'\"])([\w$\.]+)(?:[\'\"]\])?\s*\:\s*([\w$\.]+|\"[^\"]+\"|\'[^\']+\'|\{[^\}]+\})/g,
              define: /\{\{##\s*([\w\.$]+)\s*(\:|=)([\s\S]+?)#\}\}/g,
              defineParams: /^\s*([\w$]+):([\s\S]+)/,
              conditional: /\{\{\?(\?)?\s*([\s\S]*?)\s*\}\}/g,
              iterate: /\{\{~\s*(?:\}\}|([\s\S]+?)\s*\:\s*([\w$]+)\s*(?:\:\s*([\w$]+))?\s*\}\})/g,
              varname: 'it',
              strip: true,
              append: true,
              selfcontained: false,
              doNotSkipEncoded: false
            },
            template: undefined,
            compile: undefined,
            log: true
          };
          (function() {
            if (typeof globalThis === 'object') {
              return;
            }
            try {
              Object.defineProperty(Object.prototype, '__magic__', {
                get: function() {
                  return this;
                },
                configurable: true
              });
              __magic__.globalThis = __magic__;
              delete Object.prototype.__magic__;
            } catch (e) {
              window.globalThis = function() {
                if (typeof self !== 'undefined') {
                  return self;
                }
                if (typeof window !== 'undefined') {
                  return window;
                }
                if (typeof global !== 'undefined') {
                  return global;
                }
                if (typeof this !== 'undefined') {
                  return this;
                }
                throw new Error('Unable to locate global `this`');
              }();
            }
          })();
          doT.encodeHTMLSource = function(doNotSkipEncoded) {
            var encodeHTMLRules = {
              '&': '&#38;',
              '<': '&#60;',
              '>': '&#62;',
              '"': '&#34;',
              '\'': '&#39;',
              '/': '&#47;'
            }, matchHTML = doNotSkipEncoded ? /[&<>"'\/]/g : /&(?!#?\w+;)|<|>|"|'|\//g;
            return function(code) {
              return code ? code.toString().replace(matchHTML, function(m) {
                return encodeHTMLRules[m] || m;
              }) : '';
            };
          };
          if (typeof module !== 'undefined' && module.exports) {
            module.exports = doT;
          } else if (typeof define === 'function' && define.amd) {
            define(function() {
              return doT;
            });
          } else {
            globalThis.doT = doT;
          }
          var startend = {
            append: {
              start: '\'+(',
              end: ')+\'',
              startencode: '\'+encodeHTML('
            },
            split: {
              start: '\';out+=(',
              end: ');out+=\'',
              startencode: '\';out+=encodeHTML('
            }
          }, skip = /$^/;
          function resolveDefs(c, block, def) {
            return (typeof block === 'string' ? block : block.toString()).replace(c.define || skip, function(m, code, assign, value) {
              if (code.indexOf('def.') === 0) {
                code = code.substring(4);
              }
              if (!(code in def)) {
                if (assign === ':') {
                  if (c.defineParams) {
                    value.replace(c.defineParams, function(m, param, v) {
                      def[code] = {
                        arg: param,
                        text: v
                      };
                    });
                  }
                  if (!(code in def)) {
                    def[code] = value;
                  }
                } else {
                  new Function('def', 'def[\'' + code + '\']=' + value)(def);
                }
              }
              return '';
            }).replace(c.use || skip, function(m, code) {
              if (c.useParams) {
                code = code.replace(c.useParams, function(m, s, d, param) {
                  if (def[d] && def[d].arg && param) {
                    var rw = (d + ':' + param).replace(/'|\\/g, '_');
                    def.__exp = def.__exp || {};
                    def.__exp[rw] = def[d].text.replace(new RegExp('(^|[^\\w$])' + def[d].arg + '([^\\w$])', 'g'), '$1' + param + '$2');
                    return s + 'def.__exp[\'' + rw + '\']';
                  }
                });
              }
              var v = new Function('def', 'return ' + code)(def);
              return v ? resolveDefs(c, v, def) : v;
            });
          }
          function unescape(code) {
            return code.replace(/\\('|\\)/g, '$1').replace(/[\r\t\n]/g, ' ');
          }
          doT.template = function(tmpl, c, def) {
            c = c || doT.templateSettings;
            var cse = c.append ? startend.append : startend.split, needhtmlencode, sid = 0, indv, str = c.use || c.define ? resolveDefs(c, tmpl, def || {}) : tmpl;
            str = ('var out=\'' + (c.strip ? str.replace(/(^|\r|\n)\t* +| +\t*(\r|\n|$)/g, ' ').replace(/\r|\n|\t|\/\*[\s\S]*?\*\//g, '') : str).replace(/'|\\/g, '\\$&').replace(c.interpolate || skip, function(m, code) {
              return cse.start + unescape(code) + cse.end;
            }).replace(c.encode || skip, function(m, code) {
              needhtmlencode = true;
              return cse.startencode + unescape(code) + cse.end;
            }).replace(c.conditional || skip, function(m, elsecase, code) {
              return elsecase ? code ? '\';}else if(' + unescape(code) + '){out+=\'' : '\';}else{out+=\'' : code ? '\';if(' + unescape(code) + '){out+=\'' : '\';}out+=\'';
            }).replace(c.iterate || skip, function(m, iterate, vname, iname) {
              if (!iterate) {
                return '\';} } out+=\'';
              }
              sid += 1;
              indv = iname || 'i' + sid;
              iterate = unescape(iterate);
              return '\';var arr' + sid + '=' + iterate + ';if(arr' + sid + '){var ' + vname + ',' + indv + '=-1,l' + sid + '=arr' + sid + '.length-1;while(' + indv + '<l' + sid + '){' + vname + '=arr' + sid + '[' + indv + '+=1];out+=\'';
            }).replace(c.evaluate || skip, function(m, code) {
              return '\';' + unescape(code) + 'out+=\'';
            }) + '\';return out;').replace(/\n/g, '\\n').replace(/\t/g, '\\t').replace(/\r/g, '\\r').replace(/(\s|;|\}|^|\{)out\+='';/g, '$1').replace(/\+''/g, '');
            if (needhtmlencode) {
              if (!c.selfcontained && globalThis && !globalThis._encodeHTML) {
                globalThis._encodeHTML = doT.encodeHTMLSource(c.doNotSkipEncoded);
              }
              str = 'var encodeHTML = typeof _encodeHTML !== \'undefined\' ? _encodeHTML : (' + doT.encodeHTMLSource.toString() + '(' + (c.doNotSkipEncoded || '') + '));' + str;
            }
            try {
              return new Function(c.varname, str);
            } catch (e) {
              if (typeof console !== 'undefined') {
                console.log('Could not create a template function: ' + str);
              }
              throw e;
            }
          };
          doT.compile = function(tmpl, def) {
            return doT.template(tmpl, null, def);
          };
        })();
      }).call(this, typeof global !== 'undefined' ? global : typeof self !== 'undefined' ? self : typeof window !== 'undefined' ? window : {});
    }, {} ],
    3: [ function(_dereq_, module, exports) {
      module.exports = _dereq_('./lib/axios');
    }, {
      './lib/axios': 5
    } ],
    4: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./../utils');
      var settle = _dereq_('./../core/settle');
      var buildURL = _dereq_('./../helpers/buildURL');
      var buildFullPath = _dereq_('../core/buildFullPath');
      var parseHeaders = _dereq_('./../helpers/parseHeaders');
      var isURLSameOrigin = _dereq_('./../helpers/isURLSameOrigin');
      var createError = _dereq_('../core/createError');
      module.exports = function xhrAdapter(config) {
        return new Promise(function dispatchXhrRequest(resolve, reject) {
          var requestData = config.data;
          var requestHeaders = config.headers;
          if (utils.isFormData(requestData)) {
            delete requestHeaders['Content-Type'];
          }
          var request = new XMLHttpRequest();
          if (config.auth) {
            var username = config.auth.username || '';
            var password = config.auth.password || '';
            requestHeaders.Authorization = 'Basic ' + btoa(username + ':' + password);
          }
          var fullPath = buildFullPath(config.baseURL, config.url);
          request.open(config.method.toUpperCase(), buildURL(fullPath, config.params, config.paramsSerializer), true);
          request.timeout = config.timeout;
          request.onreadystatechange = function handleLoad() {
            if (!request || request.readyState !== 4) {
              return;
            }
            if (request.status === 0 && !(request.responseURL && request.responseURL.indexOf('file:') === 0)) {
              return;
            }
            var responseHeaders = 'getAllResponseHeaders' in request ? parseHeaders(request.getAllResponseHeaders()) : null;
            var responseData = !config.responseType || config.responseType === 'text' ? request.responseText : request.response;
            var response = {
              data: responseData,
              status: request.status,
              statusText: request.statusText,
              headers: responseHeaders,
              config: config,
              request: request
            };
            settle(resolve, reject, response);
            request = null;
          };
          request.onabort = function handleAbort() {
            if (!request) {
              return;
            }
            reject(createError('Request aborted', config, 'ECONNABORTED', request));
            request = null;
          };
          request.onerror = function handleError() {
            reject(createError('Network Error', config, null, request));
            request = null;
          };
          request.ontimeout = function handleTimeout() {
            var timeoutErrorMessage = 'timeout of ' + config.timeout + 'ms exceeded';
            if (config.timeoutErrorMessage) {
              timeoutErrorMessage = config.timeoutErrorMessage;
            }
            reject(createError(timeoutErrorMessage, config, 'ECONNABORTED', request));
            request = null;
          };
          if (utils.isStandardBrowserEnv()) {
            var cookies = _dereq_('./../helpers/cookies');
            var xsrfValue = (config.withCredentials || isURLSameOrigin(fullPath)) && config.xsrfCookieName ? cookies.read(config.xsrfCookieName) : undefined;
            if (xsrfValue) {
              requestHeaders[config.xsrfHeaderName] = xsrfValue;
            }
          }
          if ('setRequestHeader' in request) {
            utils.forEach(requestHeaders, function setRequestHeader(val, key) {
              if (typeof requestData === 'undefined' && key.toLowerCase() === 'content-type') {
                delete requestHeaders[key];
              } else {
                request.setRequestHeader(key, val);
              }
            });
          }
          if (!utils.isUndefined(config.withCredentials)) {
            request.withCredentials = !!config.withCredentials;
          }
          if (config.responseType) {
            try {
              request.responseType = config.responseType;
            } catch (e) {
              if (config.responseType !== 'json') {
                throw e;
              }
            }
          }
          if (typeof config.onDownloadProgress === 'function') {
            request.addEventListener('progress', config.onDownloadProgress);
          }
          if (typeof config.onUploadProgress === 'function' && request.upload) {
            request.upload.addEventListener('progress', config.onUploadProgress);
          }
          if (config.cancelToken) {
            config.cancelToken.promise.then(function onCanceled(cancel) {
              if (!request) {
                return;
              }
              request.abort();
              reject(cancel);
              request = null;
            });
          }
          if (requestData === undefined) {
            requestData = null;
          }
          request.send(requestData);
        });
      };
    }, {
      '../core/buildFullPath': 11,
      '../core/createError': 12,
      './../core/settle': 16,
      './../helpers/buildURL': 20,
      './../helpers/cookies': 22,
      './../helpers/isURLSameOrigin': 24,
      './../helpers/parseHeaders': 26,
      './../utils': 28
    } ],
    5: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./utils');
      var bind = _dereq_('./helpers/bind');
      var Axios = _dereq_('./core/Axios');
      var mergeConfig = _dereq_('./core/mergeConfig');
      var defaults = _dereq_('./defaults');
      function createInstance(defaultConfig) {
        var context = new Axios(defaultConfig);
        var instance = bind(Axios.prototype.request, context);
        utils.extend(instance, Axios.prototype, context);
        utils.extend(instance, context);
        return instance;
      }
      var axios = createInstance(defaults);
      axios.Axios = Axios;
      axios.create = function create(instanceConfig) {
        return createInstance(mergeConfig(axios.defaults, instanceConfig));
      };
      axios.Cancel = _dereq_('./cancel/Cancel');
      axios.CancelToken = _dereq_('./cancel/CancelToken');
      axios.isCancel = _dereq_('./cancel/isCancel');
      axios.all = function all(promises) {
        return Promise.all(promises);
      };
      axios.spread = _dereq_('./helpers/spread');
      module.exports = axios;
      module.exports.default = axios;
    }, {
      './cancel/Cancel': 6,
      './cancel/CancelToken': 7,
      './cancel/isCancel': 8,
      './core/Axios': 9,
      './core/mergeConfig': 15,
      './defaults': 18,
      './helpers/bind': 19,
      './helpers/spread': 27,
      './utils': 28
    } ],
    6: [ function(_dereq_, module, exports) {
      'use strict';
      function Cancel(message) {
        this.message = message;
      }
      Cancel.prototype.toString = function toString() {
        return 'Cancel' + (this.message ? ': ' + this.message : '');
      };
      Cancel.prototype.__CANCEL__ = true;
      module.exports = Cancel;
    }, {} ],
    7: [ function(_dereq_, module, exports) {
      'use strict';
      var Cancel = _dereq_('./Cancel');
      function CancelToken(executor) {
        if (typeof executor !== 'function') {
          throw new TypeError('executor must be a function.');
        }
        var resolvePromise;
        this.promise = new Promise(function promiseExecutor(resolve) {
          resolvePromise = resolve;
        });
        var token = this;
        executor(function cancel(message) {
          if (token.reason) {
            return;
          }
          token.reason = new Cancel(message);
          resolvePromise(token.reason);
        });
      }
      CancelToken.prototype.throwIfRequested = function throwIfRequested() {
        if (this.reason) {
          throw this.reason;
        }
      };
      CancelToken.source = function source() {
        var cancel;
        var token = new CancelToken(function executor(c) {
          cancel = c;
        });
        return {
          token: token,
          cancel: cancel
        };
      };
      module.exports = CancelToken;
    }, {
      './Cancel': 6
    } ],
    8: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function isCancel(value) {
        return !!(value && value.__CANCEL__);
      };
    }, {} ],
    9: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./../utils');
      var buildURL = _dereq_('../helpers/buildURL');
      var InterceptorManager = _dereq_('./InterceptorManager');
      var dispatchRequest = _dereq_('./dispatchRequest');
      var mergeConfig = _dereq_('./mergeConfig');
      function Axios(instanceConfig) {
        this.defaults = instanceConfig;
        this.interceptors = {
          request: new InterceptorManager(),
          response: new InterceptorManager()
        };
      }
      Axios.prototype.request = function request(config) {
        if (typeof config === 'string') {
          config = arguments[1] || {};
          config.url = arguments[0];
        } else {
          config = config || {};
        }
        config = mergeConfig(this.defaults, config);
        if (config.method) {
          config.method = config.method.toLowerCase();
        } else if (this.defaults.method) {
          config.method = this.defaults.method.toLowerCase();
        } else {
          config.method = 'get';
        }
        var chain = [ dispatchRequest, undefined ];
        var promise = Promise.resolve(config);
        this.interceptors.request.forEach(function unshiftRequestInterceptors(interceptor) {
          chain.unshift(interceptor.fulfilled, interceptor.rejected);
        });
        this.interceptors.response.forEach(function pushResponseInterceptors(interceptor) {
          chain.push(interceptor.fulfilled, interceptor.rejected);
        });
        while (chain.length) {
          promise = promise.then(chain.shift(), chain.shift());
        }
        return promise;
      };
      Axios.prototype.getUri = function getUri(config) {
        config = mergeConfig(this.defaults, config);
        return buildURL(config.url, config.params, config.paramsSerializer).replace(/^\?/, '');
      };
      utils.forEach([ 'delete', 'get', 'head', 'options' ], function forEachMethodNoData(method) {
        Axios.prototype[method] = function(url, config) {
          return this.request(utils.merge(config || {}, {
            method: method,
            url: url
          }));
        };
      });
      utils.forEach([ 'post', 'put', 'patch' ], function forEachMethodWithData(method) {
        Axios.prototype[method] = function(url, data, config) {
          return this.request(utils.merge(config || {}, {
            method: method,
            url: url,
            data: data
          }));
        };
      });
      module.exports = Axios;
    }, {
      '../helpers/buildURL': 20,
      './../utils': 28,
      './InterceptorManager': 10,
      './dispatchRequest': 13,
      './mergeConfig': 15
    } ],
    10: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./../utils');
      function InterceptorManager() {
        this.handlers = [];
      }
      InterceptorManager.prototype.use = function use(fulfilled, rejected) {
        this.handlers.push({
          fulfilled: fulfilled,
          rejected: rejected
        });
        return this.handlers.length - 1;
      };
      InterceptorManager.prototype.eject = function eject(id) {
        if (this.handlers[id]) {
          this.handlers[id] = null;
        }
      };
      InterceptorManager.prototype.forEach = function forEach(fn) {
        utils.forEach(this.handlers, function forEachHandler(h) {
          if (h !== null) {
            fn(h);
          }
        });
      };
      module.exports = InterceptorManager;
    }, {
      './../utils': 28
    } ],
    11: [ function(_dereq_, module, exports) {
      'use strict';
      var isAbsoluteURL = _dereq_('../helpers/isAbsoluteURL');
      var combineURLs = _dereq_('../helpers/combineURLs');
      module.exports = function buildFullPath(baseURL, requestedURL) {
        if (baseURL && !isAbsoluteURL(requestedURL)) {
          return combineURLs(baseURL, requestedURL);
        }
        return requestedURL;
      };
    }, {
      '../helpers/combineURLs': 21,
      '../helpers/isAbsoluteURL': 23
    } ],
    12: [ function(_dereq_, module, exports) {
      'use strict';
      var enhanceError = _dereq_('./enhanceError');
      module.exports = function createError(message, config, code, request, response) {
        var error = new Error(message);
        return enhanceError(error, config, code, request, response);
      };
    }, {
      './enhanceError': 14
    } ],
    13: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./../utils');
      var transformData = _dereq_('./transformData');
      var isCancel = _dereq_('../cancel/isCancel');
      var defaults = _dereq_('../defaults');
      function throwIfCancellationRequested(config) {
        if (config.cancelToken) {
          config.cancelToken.throwIfRequested();
        }
      }
      module.exports = function dispatchRequest(config) {
        throwIfCancellationRequested(config);
        config.headers = config.headers || {};
        config.data = transformData(config.data, config.headers, config.transformRequest);
        config.headers = utils.merge(config.headers.common || {}, config.headers[config.method] || {}, config.headers);
        utils.forEach([ 'delete', 'get', 'head', 'post', 'put', 'patch', 'common' ], function cleanHeaderConfig(method) {
          delete config.headers[method];
        });
        var adapter = config.adapter || defaults.adapter;
        return adapter(config).then(function onAdapterResolution(response) {
          throwIfCancellationRequested(config);
          response.data = transformData(response.data, response.headers, config.transformResponse);
          return response;
        }, function onAdapterRejection(reason) {
          if (!isCancel(reason)) {
            throwIfCancellationRequested(config);
            if (reason && reason.response) {
              reason.response.data = transformData(reason.response.data, reason.response.headers, config.transformResponse);
            }
          }
          return Promise.reject(reason);
        });
      };
    }, {
      '../cancel/isCancel': 8,
      '../defaults': 18,
      './../utils': 28,
      './transformData': 17
    } ],
    14: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function enhanceError(error, config, code, request, response) {
        error.config = config;
        if (code) {
          error.code = code;
        }
        error.request = request;
        error.response = response;
        error.isAxiosError = true;
        error.toJSON = function() {
          return {
            message: this.message,
            name: this.name,
            description: this.description,
            number: this.number,
            fileName: this.fileName,
            lineNumber: this.lineNumber,
            columnNumber: this.columnNumber,
            stack: this.stack,
            config: this.config,
            code: this.code
          };
        };
        return error;
      };
    }, {} ],
    15: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('../utils');
      module.exports = function mergeConfig(config1, config2) {
        config2 = config2 || {};
        var config = {};
        var valueFromConfig2Keys = [ 'url', 'method', 'params', 'data' ];
        var mergeDeepPropertiesKeys = [ 'headers', 'auth', 'proxy' ];
        var defaultToConfig2Keys = [ 'baseURL', 'url', 'transformRequest', 'transformResponse', 'paramsSerializer', 'timeout', 'withCredentials', 'adapter', 'responseType', 'xsrfCookieName', 'xsrfHeaderName', 'onUploadProgress', 'onDownloadProgress', 'maxContentLength', 'validateStatus', 'maxRedirects', 'httpAgent', 'httpsAgent', 'cancelToken', 'socketPath' ];
        utils.forEach(valueFromConfig2Keys, function valueFromConfig2(prop) {
          if (typeof config2[prop] !== 'undefined') {
            config[prop] = config2[prop];
          }
        });
        utils.forEach(mergeDeepPropertiesKeys, function mergeDeepProperties(prop) {
          if (utils.isObject(config2[prop])) {
            config[prop] = utils.deepMerge(config1[prop], config2[prop]);
          } else if (typeof config2[prop] !== 'undefined') {
            config[prop] = config2[prop];
          } else if (utils.isObject(config1[prop])) {
            config[prop] = utils.deepMerge(config1[prop]);
          } else if (typeof config1[prop] !== 'undefined') {
            config[prop] = config1[prop];
          }
        });
        utils.forEach(defaultToConfig2Keys, function defaultToConfig2(prop) {
          if (typeof config2[prop] !== 'undefined') {
            config[prop] = config2[prop];
          } else if (typeof config1[prop] !== 'undefined') {
            config[prop] = config1[prop];
          }
        });
        var axiosKeys = valueFromConfig2Keys.concat(mergeDeepPropertiesKeys).concat(defaultToConfig2Keys);
        var otherKeys = Object.keys(config2).filter(function filterAxiosKeys(key) {
          return axiosKeys.indexOf(key) === -1;
        });
        utils.forEach(otherKeys, function otherKeysDefaultToConfig2(prop) {
          if (typeof config2[prop] !== 'undefined') {
            config[prop] = config2[prop];
          } else if (typeof config1[prop] !== 'undefined') {
            config[prop] = config1[prop];
          }
        });
        return config;
      };
    }, {
      '../utils': 28
    } ],
    16: [ function(_dereq_, module, exports) {
      'use strict';
      var createError = _dereq_('./createError');
      module.exports = function settle(resolve, reject, response) {
        var validateStatus = response.config.validateStatus;
        if (!validateStatus || validateStatus(response.status)) {
          resolve(response);
        } else {
          reject(createError('Request failed with status code ' + response.status, response.config, null, response.request, response));
        }
      };
    }, {
      './createError': 12
    } ],
    17: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./../utils');
      module.exports = function transformData(data, headers, fns) {
        utils.forEach(fns, function transform(fn) {
          data = fn(data, headers);
        });
        return data;
      };
    }, {
      './../utils': 28
    } ],
    18: [ function(_dereq_, module, exports) {
      (function(process) {
        'use strict';
        var utils = _dereq_('./utils');
        var normalizeHeaderName = _dereq_('./helpers/normalizeHeaderName');
        var DEFAULT_CONTENT_TYPE = {
          'Content-Type': 'application/x-www-form-urlencoded'
        };
        function setContentTypeIfUnset(headers, value) {
          if (!utils.isUndefined(headers) && utils.isUndefined(headers['Content-Type'])) {
            headers['Content-Type'] = value;
          }
        }
        function getDefaultAdapter() {
          var adapter;
          if (typeof XMLHttpRequest !== 'undefined') {
            adapter = _dereq_('./adapters/xhr');
          } else if (typeof process !== 'undefined' && Object.prototype.toString.call(process) === '[object process]') {
            adapter = _dereq_('./adapters/http');
          }
          return adapter;
        }
        var defaults = {
          adapter: getDefaultAdapter(),
          transformRequest: [ function transformRequest(data, headers) {
            normalizeHeaderName(headers, 'Accept');
            normalizeHeaderName(headers, 'Content-Type');
            if (utils.isFormData(data) || utils.isArrayBuffer(data) || utils.isBuffer(data) || utils.isStream(data) || utils.isFile(data) || utils.isBlob(data)) {
              return data;
            }
            if (utils.isArrayBufferView(data)) {
              return data.buffer;
            }
            if (utils.isURLSearchParams(data)) {
              setContentTypeIfUnset(headers, 'application/x-www-form-urlencoded;charset=utf-8');
              return data.toString();
            }
            if (utils.isObject(data)) {
              setContentTypeIfUnset(headers, 'application/json;charset=utf-8');
              return JSON.stringify(data);
            }
            return data;
          } ],
          transformResponse: [ function transformResponse(data) {
            if (typeof data === 'string') {
              try {
                data = JSON.parse(data);
              } catch (e) {}
            }
            return data;
          } ],
          timeout: 0,
          xsrfCookieName: 'XSRF-TOKEN',
          xsrfHeaderName: 'X-XSRF-TOKEN',
          maxContentLength: -1,
          validateStatus: function validateStatus(status) {
            return status >= 200 && status < 300;
          }
        };
        defaults.headers = {
          common: {
            Accept: 'application/json, text/plain, */*'
          }
        };
        utils.forEach([ 'delete', 'get', 'head' ], function forEachMethodNoData(method) {
          defaults.headers[method] = {};
        });
        utils.forEach([ 'post', 'put', 'patch' ], function forEachMethodWithData(method) {
          defaults.headers[method] = utils.merge(DEFAULT_CONTENT_TYPE);
        });
        module.exports = defaults;
      }).call(this, _dereq_('_process'));
    }, {
      './adapters/http': 4,
      './adapters/xhr': 4,
      './helpers/normalizeHeaderName': 25,
      './utils': 28,
      _process: 236
    } ],
    19: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function bind(fn, thisArg) {
        return function wrap() {
          var args = new Array(arguments.length);
          for (var i = 0; i < args.length; i++) {
            args[i] = arguments[i];
          }
          return fn.apply(thisArg, args);
        };
      };
    }, {} ],
    20: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./../utils');
      function encode(val) {
        return encodeURIComponent(val).replace(/%40/gi, '@').replace(/%3A/gi, ':').replace(/%24/g, '$').replace(/%2C/gi, ',').replace(/%20/g, '+').replace(/%5B/gi, '[').replace(/%5D/gi, ']');
      }
      module.exports = function buildURL(url, params, paramsSerializer) {
        if (!params) {
          return url;
        }
        var serializedParams;
        if (paramsSerializer) {
          serializedParams = paramsSerializer(params);
        } else if (utils.isURLSearchParams(params)) {
          serializedParams = params.toString();
        } else {
          var parts = [];
          utils.forEach(params, function serialize(val, key) {
            if (val === null || typeof val === 'undefined') {
              return;
            }
            if (utils.isArray(val)) {
              key = key + '[]';
            } else {
              val = [ val ];
            }
            utils.forEach(val, function parseValue(v) {
              if (utils.isDate(v)) {
                v = v.toISOString();
              } else if (utils.isObject(v)) {
                v = JSON.stringify(v);
              }
              parts.push(encode(key) + '=' + encode(v));
            });
          });
          serializedParams = parts.join('&');
        }
        if (serializedParams) {
          var hashmarkIndex = url.indexOf('#');
          if (hashmarkIndex !== -1) {
            url = url.slice(0, hashmarkIndex);
          }
          url += (url.indexOf('?') === -1 ? '?' : '&') + serializedParams;
        }
        return url;
      };
    }, {
      './../utils': 28
    } ],
    21: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function combineURLs(baseURL, relativeURL) {
        return relativeURL ? baseURL.replace(/\/+$/, '') + '/' + relativeURL.replace(/^\/+/, '') : baseURL;
      };
    }, {} ],
    22: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./../utils');
      module.exports = utils.isStandardBrowserEnv() ? function standardBrowserEnv() {
        return {
          write: function write(name, value, expires, path, domain, secure) {
            var cookie = [];
            cookie.push(name + '=' + encodeURIComponent(value));
            if (utils.isNumber(expires)) {
              cookie.push('expires=' + new Date(expires).toGMTString());
            }
            if (utils.isString(path)) {
              cookie.push('path=' + path);
            }
            if (utils.isString(domain)) {
              cookie.push('domain=' + domain);
            }
            if (secure === true) {
              cookie.push('secure');
            }
            document.cookie = cookie.join('; ');
          },
          read: function read(name) {
            var match = document.cookie.match(new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'));
            return match ? decodeURIComponent(match[3]) : null;
          },
          remove: function remove(name) {
            this.write(name, '', Date.now() - 864e5);
          }
        };
      }() : function nonStandardBrowserEnv() {
        return {
          write: function write() {},
          read: function read() {
            return null;
          },
          remove: function remove() {}
        };
      }();
    }, {
      './../utils': 28
    } ],
    23: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function isAbsoluteURL(url) {
        return /^([a-z][a-z\d\+\-\.]*:)?\/\//i.test(url);
      };
    }, {} ],
    24: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./../utils');
      module.exports = utils.isStandardBrowserEnv() ? function standardBrowserEnv() {
        var msie = /(msie|trident)/i.test(navigator.userAgent);
        var urlParsingNode = document.createElement('a');
        var originURL;
        function resolveURL(url) {
          var href = url;
          if (msie) {
            urlParsingNode.setAttribute('href', href);
            href = urlParsingNode.href;
          }
          urlParsingNode.setAttribute('href', href);
          return {
            href: urlParsingNode.href,
            protocol: urlParsingNode.protocol ? urlParsingNode.protocol.replace(/:$/, '') : '',
            host: urlParsingNode.host,
            search: urlParsingNode.search ? urlParsingNode.search.replace(/^\?/, '') : '',
            hash: urlParsingNode.hash ? urlParsingNode.hash.replace(/^#/, '') : '',
            hostname: urlParsingNode.hostname,
            port: urlParsingNode.port,
            pathname: urlParsingNode.pathname.charAt(0) === '/' ? urlParsingNode.pathname : '/' + urlParsingNode.pathname
          };
        }
        originURL = resolveURL(window.location.href);
        return function isURLSameOrigin(requestURL) {
          var parsed = utils.isString(requestURL) ? resolveURL(requestURL) : requestURL;
          return parsed.protocol === originURL.protocol && parsed.host === originURL.host;
        };
      }() : function nonStandardBrowserEnv() {
        return function isURLSameOrigin() {
          return true;
        };
      }();
    }, {
      './../utils': 28
    } ],
    25: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('../utils');
      module.exports = function normalizeHeaderName(headers, normalizedName) {
        utils.forEach(headers, function processHeader(value, name) {
          if (name !== normalizedName && name.toUpperCase() === normalizedName.toUpperCase()) {
            headers[normalizedName] = value;
            delete headers[name];
          }
        });
      };
    }, {
      '../utils': 28
    } ],
    26: [ function(_dereq_, module, exports) {
      'use strict';
      var utils = _dereq_('./../utils');
      var ignoreDuplicateOf = [ 'age', 'authorization', 'content-length', 'content-type', 'etag', 'expires', 'from', 'host', 'if-modified-since', 'if-unmodified-since', 'last-modified', 'location', 'max-forwards', 'proxy-authorization', 'referer', 'retry-after', 'user-agent' ];
      module.exports = function parseHeaders(headers) {
        var parsed = {};
        var key;
        var val;
        var i;
        if (!headers) {
          return parsed;
        }
        utils.forEach(headers.split('\n'), function parser(line) {
          i = line.indexOf(':');
          key = utils.trim(line.substr(0, i)).toLowerCase();
          val = utils.trim(line.substr(i + 1));
          if (key) {
            if (parsed[key] && ignoreDuplicateOf.indexOf(key) >= 0) {
              return;
            }
            if (key === 'set-cookie') {
              parsed[key] = (parsed[key] ? parsed[key] : []).concat([ val ]);
            } else {
              parsed[key] = parsed[key] ? parsed[key] + ', ' + val : val;
            }
          }
        });
        return parsed;
      };
    }, {
      './../utils': 28
    } ],
    27: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function spread(callback) {
        return function wrap(arr) {
          return callback.apply(null, arr);
        };
      };
    }, {} ],
    28: [ function(_dereq_, module, exports) {
      'use strict';
      var bind = _dereq_('./helpers/bind');
      var toString = Object.prototype.toString;
      function isArray(val) {
        return toString.call(val) === '[object Array]';
      }
      function isUndefined(val) {
        return typeof val === 'undefined';
      }
      function isBuffer(val) {
        return val !== null && !isUndefined(val) && val.constructor !== null && !isUndefined(val.constructor) && typeof val.constructor.isBuffer === 'function' && val.constructor.isBuffer(val);
      }
      function isArrayBuffer(val) {
        return toString.call(val) === '[object ArrayBuffer]';
      }
      function isFormData(val) {
        return typeof FormData !== 'undefined' && val instanceof FormData;
      }
      function isArrayBufferView(val) {
        var result;
        if (typeof ArrayBuffer !== 'undefined' && ArrayBuffer.isView) {
          result = ArrayBuffer.isView(val);
        } else {
          result = val && val.buffer && val.buffer instanceof ArrayBuffer;
        }
        return result;
      }
      function isString(val) {
        return typeof val === 'string';
      }
      function isNumber(val) {
        return typeof val === 'number';
      }
      function isObject(val) {
        return val !== null && typeof val === 'object';
      }
      function isDate(val) {
        return toString.call(val) === '[object Date]';
      }
      function isFile(val) {
        return toString.call(val) === '[object File]';
      }
      function isBlob(val) {
        return toString.call(val) === '[object Blob]';
      }
      function isFunction(val) {
        return toString.call(val) === '[object Function]';
      }
      function isStream(val) {
        return isObject(val) && isFunction(val.pipe);
      }
      function isURLSearchParams(val) {
        return typeof URLSearchParams !== 'undefined' && val instanceof URLSearchParams;
      }
      function trim(str) {
        return str.replace(/^\s*/, '').replace(/\s*$/, '');
      }
      function isStandardBrowserEnv() {
        if (typeof navigator !== 'undefined' && (navigator.product === 'ReactNative' || navigator.product === 'NativeScript' || navigator.product === 'NS')) {
          return false;
        }
        return typeof window !== 'undefined' && typeof document !== 'undefined';
      }
      function forEach(obj, fn) {
        if (obj === null || typeof obj === 'undefined') {
          return;
        }
        if (typeof obj !== 'object') {
          obj = [ obj ];
        }
        if (isArray(obj)) {
          for (var i = 0, l = obj.length; i < l; i++) {
            fn.call(null, obj[i], i, obj);
          }
        } else {
          for (var key in obj) {
            if (Object.prototype.hasOwnProperty.call(obj, key)) {
              fn.call(null, obj[key], key, obj);
            }
          }
        }
      }
      function merge() {
        var result = {};
        function assignValue(val, key) {
          if (typeof result[key] === 'object' && typeof val === 'object') {
            result[key] = merge(result[key], val);
          } else {
            result[key] = val;
          }
        }
        for (var i = 0, l = arguments.length; i < l; i++) {
          forEach(arguments[i], assignValue);
        }
        return result;
      }
      function deepMerge() {
        var result = {};
        function assignValue(val, key) {
          if (typeof result[key] === 'object' && typeof val === 'object') {
            result[key] = deepMerge(result[key], val);
          } else if (typeof val === 'object') {
            result[key] = deepMerge({}, val);
          } else {
            result[key] = val;
          }
        }
        for (var i = 0, l = arguments.length; i < l; i++) {
          forEach(arguments[i], assignValue);
        }
        return result;
      }
      function extend(a, b, thisArg) {
        forEach(b, function assignValue(val, key) {
          if (thisArg && typeof val === 'function') {
            a[key] = bind(val, thisArg);
          } else {
            a[key] = val;
          }
        });
        return a;
      }
      module.exports = {
        isArray: isArray,
        isArrayBuffer: isArrayBuffer,
        isBuffer: isBuffer,
        isFormData: isFormData,
        isArrayBufferView: isArrayBufferView,
        isString: isString,
        isNumber: isNumber,
        isObject: isObject,
        isUndefined: isUndefined,
        isDate: isDate,
        isFile: isFile,
        isBlob: isBlob,
        isFunction: isFunction,
        isStream: isStream,
        isURLSearchParams: isURLSearchParams,
        isStandardBrowserEnv: isStandardBrowserEnv,
        forEach: forEach,
        merge: merge,
        deepMerge: deepMerge,
        extend: extend,
        trim: trim
      };
    }, {
      './helpers/bind': 19
    } ],
    29: [ function(_dereq_, module, exports) {
      _dereq_('../../modules/es.typed-array.from');
      _dereq_('../../modules/es.typed-array.of');
      _dereq_('../../modules/es.typed-array.copy-within');
      _dereq_('../../modules/es.typed-array.every');
      _dereq_('../../modules/es.typed-array.fill');
      _dereq_('../../modules/es.typed-array.filter');
      _dereq_('../../modules/es.typed-array.find');
      _dereq_('../../modules/es.typed-array.find-index');
      _dereq_('../../modules/es.typed-array.for-each');
      _dereq_('../../modules/es.typed-array.includes');
      _dereq_('../../modules/es.typed-array.index-of');
      _dereq_('../../modules/es.typed-array.join');
      _dereq_('../../modules/es.typed-array.last-index-of');
      _dereq_('../../modules/es.typed-array.map');
      _dereq_('../../modules/es.typed-array.reduce');
      _dereq_('../../modules/es.typed-array.reduce-right');
      _dereq_('../../modules/es.typed-array.reverse');
      _dereq_('../../modules/es.typed-array.set');
      _dereq_('../../modules/es.typed-array.slice');
      _dereq_('../../modules/es.typed-array.some');
      _dereq_('../../modules/es.typed-array.sort');
      _dereq_('../../modules/es.typed-array.subarray');
      _dereq_('../../modules/es.typed-array.to-locale-string');
      _dereq_('../../modules/es.typed-array.to-string');
      _dereq_('../../modules/es.typed-array.iterator');
      _dereq_('../../modules/es.object.to-string');
    }, {
      '../../modules/es.object.to-string': 128,
      '../../modules/es.typed-array.copy-within': 129,
      '../../modules/es.typed-array.every': 130,
      '../../modules/es.typed-array.fill': 131,
      '../../modules/es.typed-array.filter': 132,
      '../../modules/es.typed-array.find': 134,
      '../../modules/es.typed-array.find-index': 133,
      '../../modules/es.typed-array.for-each': 135,
      '../../modules/es.typed-array.from': 136,
      '../../modules/es.typed-array.includes': 137,
      '../../modules/es.typed-array.index-of': 138,
      '../../modules/es.typed-array.iterator': 139,
      '../../modules/es.typed-array.join': 140,
      '../../modules/es.typed-array.last-index-of': 141,
      '../../modules/es.typed-array.map': 142,
      '../../modules/es.typed-array.of': 143,
      '../../modules/es.typed-array.reduce': 145,
      '../../modules/es.typed-array.reduce-right': 144,
      '../../modules/es.typed-array.reverse': 146,
      '../../modules/es.typed-array.set': 147,
      '../../modules/es.typed-array.slice': 148,
      '../../modules/es.typed-array.some': 149,
      '../../modules/es.typed-array.sort': 150,
      '../../modules/es.typed-array.subarray': 151,
      '../../modules/es.typed-array.to-locale-string': 152,
      '../../modules/es.typed-array.to-string': 153
    } ],
    30: [ function(_dereq_, module, exports) {
      _dereq_('../../modules/es.typed-array.uint32-array');
      _dereq_('./methods');
      var global = _dereq_('../../internals/global');
      module.exports = global.Uint32Array;
    }, {
      '../../internals/global': 68,
      '../../modules/es.typed-array.uint32-array': 154,
      './methods': 29
    } ],
    31: [ function(_dereq_, module, exports) {
      _dereq_('../../modules/es.typed-array.reduce');
    }, {
      '../../modules/es.typed-array.reduce': 145
    } ],
    32: [ function(_dereq_, module, exports) {
      _dereq_('../../modules/es.typed-array.some');
    }, {
      '../../modules/es.typed-array.some': 149
    } ],
    33: [ function(_dereq_, module, exports) {
      var parent = _dereq_('../../es/typed-array/uint32-array');
      module.exports = parent;
    }, {
      '../../es/typed-array/uint32-array': 30
    } ],
    34: [ function(_dereq_, module, exports) {
      module.exports = function(it) {
        if (typeof it != 'function') {
          throw TypeError(String(it) + ' is not a function');
        }
        return it;
      };
    }, {} ],
    35: [ function(_dereq_, module, exports) {
      var isObject = _dereq_('../internals/is-object');
      module.exports = function(it) {
        if (!isObject(it) && it !== null) {
          throw TypeError('Can\'t set ' + String(it) + ' as a prototype');
        }
        return it;
      };
    }, {
      '../internals/is-object': 81
    } ],
    36: [ function(_dereq_, module, exports) {
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var create = _dereq_('../internals/object-create');
      var definePropertyModule = _dereq_('../internals/object-define-property');
      var UNSCOPABLES = wellKnownSymbol('unscopables');
      var ArrayPrototype = Array.prototype;
      if (ArrayPrototype[UNSCOPABLES] == undefined) {
        definePropertyModule.f(ArrayPrototype, UNSCOPABLES, {
          configurable: true,
          value: create(null)
        });
      }
      module.exports = function(key) {
        ArrayPrototype[UNSCOPABLES][key] = true;
      };
    }, {
      '../internals/object-create': 87,
      '../internals/object-define-property': 89,
      '../internals/well-known-symbol': 126
    } ],
    37: [ function(_dereq_, module, exports) {
      module.exports = function(it, Constructor, name) {
        if (!(it instanceof Constructor)) {
          throw TypeError('Incorrect ' + (name ? name + ' ' : '') + 'invocation');
        }
        return it;
      };
    }, {} ],
    38: [ function(_dereq_, module, exports) {
      var isObject = _dereq_('../internals/is-object');
      module.exports = function(it) {
        if (!isObject(it)) {
          throw TypeError(String(it) + ' is not an object');
        }
        return it;
      };
    }, {
      '../internals/is-object': 81
    } ],
    39: [ function(_dereq_, module, exports) {
      module.exports = typeof ArrayBuffer !== 'undefined' && typeof DataView !== 'undefined';
    }, {} ],
    40: [ function(_dereq_, module, exports) {
      'use strict';
      var NATIVE_ARRAY_BUFFER = _dereq_('../internals/array-buffer-native');
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var global = _dereq_('../internals/global');
      var isObject = _dereq_('../internals/is-object');
      var has = _dereq_('../internals/has');
      var classof = _dereq_('../internals/classof');
      var createNonEnumerableProperty = _dereq_('../internals/create-non-enumerable-property');
      var redefine = _dereq_('../internals/redefine');
      var defineProperty = _dereq_('../internals/object-define-property').f;
      var getPrototypeOf = _dereq_('../internals/object-get-prototype-of');
      var setPrototypeOf = _dereq_('../internals/object-set-prototype-of');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var uid = _dereq_('../internals/uid');
      var Int8Array = global.Int8Array;
      var Int8ArrayPrototype = Int8Array && Int8Array.prototype;
      var Uint8ClampedArray = global.Uint8ClampedArray;
      var Uint8ClampedArrayPrototype = Uint8ClampedArray && Uint8ClampedArray.prototype;
      var TypedArray = Int8Array && getPrototypeOf(Int8Array);
      var TypedArrayPrototype = Int8ArrayPrototype && getPrototypeOf(Int8ArrayPrototype);
      var ObjectPrototype = Object.prototype;
      var isPrototypeOf = ObjectPrototype.isPrototypeOf;
      var TO_STRING_TAG = wellKnownSymbol('toStringTag');
      var TYPED_ARRAY_TAG = uid('TYPED_ARRAY_TAG');
      var NATIVE_ARRAY_BUFFER_VIEWS = NATIVE_ARRAY_BUFFER && !!setPrototypeOf && classof(global.opera) !== 'Opera';
      var TYPED_ARRAY_TAG_REQIRED = false;
      var NAME;
      var TypedArrayConstructorsList = {
        Int8Array: 1,
        Uint8Array: 1,
        Uint8ClampedArray: 1,
        Int16Array: 2,
        Uint16Array: 2,
        Int32Array: 4,
        Uint32Array: 4,
        Float32Array: 4,
        Float64Array: 8
      };
      var isView = function isView(it) {
        var klass = classof(it);
        return klass === 'DataView' || has(TypedArrayConstructorsList, klass);
      };
      var isTypedArray = function(it) {
        return isObject(it) && has(TypedArrayConstructorsList, classof(it));
      };
      var aTypedArray = function(it) {
        if (isTypedArray(it)) {
          return it;
        }
        throw TypeError('Target is not a typed array');
      };
      var aTypedArrayConstructor = function(C) {
        if (setPrototypeOf) {
          if (isPrototypeOf.call(TypedArray, C)) {
            return C;
          }
        } else {
          for (var ARRAY in TypedArrayConstructorsList) {
            if (has(TypedArrayConstructorsList, NAME)) {
              var TypedArrayConstructor = global[ARRAY];
              if (TypedArrayConstructor && (C === TypedArrayConstructor || isPrototypeOf.call(TypedArrayConstructor, C))) {
                return C;
              }
            }
          }
        }
        throw TypeError('Target is not a typed array constructor');
      };
      var exportTypedArrayMethod = function(KEY, property, forced) {
        if (!DESCRIPTORS) {
          return;
        }
        if (forced) {
          for (var ARRAY in TypedArrayConstructorsList) {
            var TypedArrayConstructor = global[ARRAY];
            if (TypedArrayConstructor && has(TypedArrayConstructor.prototype, KEY)) {
              delete TypedArrayConstructor.prototype[KEY];
            }
          }
        }
        if (!TypedArrayPrototype[KEY] || forced) {
          redefine(TypedArrayPrototype, KEY, forced ? property : NATIVE_ARRAY_BUFFER_VIEWS && Int8ArrayPrototype[KEY] || property);
        }
      };
      var exportTypedArrayStaticMethod = function(KEY, property, forced) {
        var ARRAY, TypedArrayConstructor;
        if (!DESCRIPTORS) {
          return;
        }
        if (setPrototypeOf) {
          if (forced) {
            for (ARRAY in TypedArrayConstructorsList) {
              TypedArrayConstructor = global[ARRAY];
              if (TypedArrayConstructor && has(TypedArrayConstructor, KEY)) {
                delete TypedArrayConstructor[KEY];
              }
            }
          }
          if (!TypedArray[KEY] || forced) {
            try {
              return redefine(TypedArray, KEY, forced ? property : NATIVE_ARRAY_BUFFER_VIEWS && Int8Array[KEY] || property);
            } catch (error) {}
          } else {
            return;
          }
        }
        for (ARRAY in TypedArrayConstructorsList) {
          TypedArrayConstructor = global[ARRAY];
          if (TypedArrayConstructor && (!TypedArrayConstructor[KEY] || forced)) {
            redefine(TypedArrayConstructor, KEY, property);
          }
        }
      };
      for (NAME in TypedArrayConstructorsList) {
        if (!global[NAME]) {
          NATIVE_ARRAY_BUFFER_VIEWS = false;
        }
      }
      if (!NATIVE_ARRAY_BUFFER_VIEWS || typeof TypedArray != 'function' || TypedArray === Function.prototype) {
        TypedArray = function TypedArray() {
          throw TypeError('Incorrect invocation');
        };
        if (NATIVE_ARRAY_BUFFER_VIEWS) {
          for (NAME in TypedArrayConstructorsList) {
            if (global[NAME]) {
              setPrototypeOf(global[NAME], TypedArray);
            }
          }
        }
      }
      if (!NATIVE_ARRAY_BUFFER_VIEWS || !TypedArrayPrototype || TypedArrayPrototype === ObjectPrototype) {
        TypedArrayPrototype = TypedArray.prototype;
        if (NATIVE_ARRAY_BUFFER_VIEWS) {
          for (NAME in TypedArrayConstructorsList) {
            if (global[NAME]) {
              setPrototypeOf(global[NAME].prototype, TypedArrayPrototype);
            }
          }
        }
      }
      if (NATIVE_ARRAY_BUFFER_VIEWS && getPrototypeOf(Uint8ClampedArrayPrototype) !== TypedArrayPrototype) {
        setPrototypeOf(Uint8ClampedArrayPrototype, TypedArrayPrototype);
      }
      if (DESCRIPTORS && !has(TypedArrayPrototype, TO_STRING_TAG)) {
        TYPED_ARRAY_TAG_REQIRED = true;
        defineProperty(TypedArrayPrototype, TO_STRING_TAG, {
          get: function() {
            return isObject(this) ? this[TYPED_ARRAY_TAG] : undefined;
          }
        });
        for (NAME in TypedArrayConstructorsList) {
          if (global[NAME]) {
            createNonEnumerableProperty(global[NAME], TYPED_ARRAY_TAG, NAME);
          }
        }
      }
      module.exports = {
        NATIVE_ARRAY_BUFFER_VIEWS: NATIVE_ARRAY_BUFFER_VIEWS,
        TYPED_ARRAY_TAG: TYPED_ARRAY_TAG_REQIRED && TYPED_ARRAY_TAG,
        aTypedArray: aTypedArray,
        aTypedArrayConstructor: aTypedArrayConstructor,
        exportTypedArrayMethod: exportTypedArrayMethod,
        exportTypedArrayStaticMethod: exportTypedArrayStaticMethod,
        isView: isView,
        isTypedArray: isTypedArray,
        TypedArray: TypedArray,
        TypedArrayPrototype: TypedArrayPrototype
      };
    }, {
      '../internals/array-buffer-native': 39,
      '../internals/classof': 53,
      '../internals/create-non-enumerable-property': 57,
      '../internals/descriptors': 60,
      '../internals/global': 68,
      '../internals/has': 69,
      '../internals/is-object': 81,
      '../internals/object-define-property': 89,
      '../internals/object-get-prototype-of': 93,
      '../internals/object-set-prototype-of': 97,
      '../internals/redefine': 102,
      '../internals/uid': 124,
      '../internals/well-known-symbol': 126
    } ],
    41: [ function(_dereq_, module, exports) {
      'use strict';
      var global = _dereq_('../internals/global');
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var NATIVE_ARRAY_BUFFER = _dereq_('../internals/array-buffer-native');
      var createNonEnumerableProperty = _dereq_('../internals/create-non-enumerable-property');
      var redefineAll = _dereq_('../internals/redefine-all');
      var fails = _dereq_('../internals/fails');
      var anInstance = _dereq_('../internals/an-instance');
      var toInteger = _dereq_('../internals/to-integer');
      var toLength = _dereq_('../internals/to-length');
      var toIndex = _dereq_('../internals/to-index');
      var IEEE754 = _dereq_('../internals/ieee754');
      var getPrototypeOf = _dereq_('../internals/object-get-prototype-of');
      var setPrototypeOf = _dereq_('../internals/object-set-prototype-of');
      var getOwnPropertyNames = _dereq_('../internals/object-get-own-property-names').f;
      var defineProperty = _dereq_('../internals/object-define-property').f;
      var arrayFill = _dereq_('../internals/array-fill');
      var setToStringTag = _dereq_('../internals/set-to-string-tag');
      var InternalStateModule = _dereq_('../internals/internal-state');
      var getInternalState = InternalStateModule.get;
      var setInternalState = InternalStateModule.set;
      var ARRAY_BUFFER = 'ArrayBuffer';
      var DATA_VIEW = 'DataView';
      var PROTOTYPE = 'prototype';
      var WRONG_LENGTH = 'Wrong length';
      var WRONG_INDEX = 'Wrong index';
      var NativeArrayBuffer = global[ARRAY_BUFFER];
      var $ArrayBuffer = NativeArrayBuffer;
      var $DataView = global[DATA_VIEW];
      var $DataViewPrototype = $DataView && $DataView[PROTOTYPE];
      var ObjectPrototype = Object.prototype;
      var RangeError = global.RangeError;
      var packIEEE754 = IEEE754.pack;
      var unpackIEEE754 = IEEE754.unpack;
      var packInt8 = function(number) {
        return [ number & 255 ];
      };
      var packInt16 = function(number) {
        return [ number & 255, number >> 8 & 255 ];
      };
      var packInt32 = function(number) {
        return [ number & 255, number >> 8 & 255, number >> 16 & 255, number >> 24 & 255 ];
      };
      var unpackInt32 = function(buffer) {
        return buffer[3] << 24 | buffer[2] << 16 | buffer[1] << 8 | buffer[0];
      };
      var packFloat32 = function(number) {
        return packIEEE754(number, 23, 4);
      };
      var packFloat64 = function(number) {
        return packIEEE754(number, 52, 8);
      };
      var addGetter = function(Constructor, key) {
        defineProperty(Constructor[PROTOTYPE], key, {
          get: function() {
            return getInternalState(this)[key];
          }
        });
      };
      var get = function(view, count, index, isLittleEndian) {
        var intIndex = toIndex(index);
        var store = getInternalState(view);
        if (intIndex + count > store.byteLength) {
          throw RangeError(WRONG_INDEX);
        }
        var bytes = getInternalState(store.buffer).bytes;
        var start = intIndex + store.byteOffset;
        var pack = bytes.slice(start, start + count);
        return isLittleEndian ? pack : pack.reverse();
      };
      var set = function(view, count, index, conversion, value, isLittleEndian) {
        var intIndex = toIndex(index);
        var store = getInternalState(view);
        if (intIndex + count > store.byteLength) {
          throw RangeError(WRONG_INDEX);
        }
        var bytes = getInternalState(store.buffer).bytes;
        var start = intIndex + store.byteOffset;
        var pack = conversion(+value);
        for (var i = 0; i < count; i++) {
          bytes[start + i] = pack[isLittleEndian ? i : count - i - 1];
        }
      };
      if (!NATIVE_ARRAY_BUFFER) {
        $ArrayBuffer = function ArrayBuffer(length) {
          anInstance(this, $ArrayBuffer, ARRAY_BUFFER);
          var byteLength = toIndex(length);
          setInternalState(this, {
            bytes: arrayFill.call(new Array(byteLength), 0),
            byteLength: byteLength
          });
          if (!DESCRIPTORS) {
            this.byteLength = byteLength;
          }
        };
        $DataView = function DataView(buffer, byteOffset, byteLength) {
          anInstance(this, $DataView, DATA_VIEW);
          anInstance(buffer, $ArrayBuffer, DATA_VIEW);
          var bufferLength = getInternalState(buffer).byteLength;
          var offset = toInteger(byteOffset);
          if (offset < 0 || offset > bufferLength) {
            throw RangeError('Wrong offset');
          }
          byteLength = byteLength === undefined ? bufferLength - offset : toLength(byteLength);
          if (offset + byteLength > bufferLength) {
            throw RangeError(WRONG_LENGTH);
          }
          setInternalState(this, {
            buffer: buffer,
            byteLength: byteLength,
            byteOffset: offset
          });
          if (!DESCRIPTORS) {
            this.buffer = buffer;
            this.byteLength = byteLength;
            this.byteOffset = offset;
          }
        };
        if (DESCRIPTORS) {
          addGetter($ArrayBuffer, 'byteLength');
          addGetter($DataView, 'buffer');
          addGetter($DataView, 'byteLength');
          addGetter($DataView, 'byteOffset');
        }
        redefineAll($DataView[PROTOTYPE], {
          getInt8: function getInt8(byteOffset) {
            return get(this, 1, byteOffset)[0] << 24 >> 24;
          },
          getUint8: function getUint8(byteOffset) {
            return get(this, 1, byteOffset)[0];
          },
          getInt16: function getInt16(byteOffset) {
            var bytes = get(this, 2, byteOffset, arguments.length > 1 ? arguments[1] : undefined);
            return (bytes[1] << 8 | bytes[0]) << 16 >> 16;
          },
          getUint16: function getUint16(byteOffset) {
            var bytes = get(this, 2, byteOffset, arguments.length > 1 ? arguments[1] : undefined);
            return bytes[1] << 8 | bytes[0];
          },
          getInt32: function getInt32(byteOffset) {
            return unpackInt32(get(this, 4, byteOffset, arguments.length > 1 ? arguments[1] : undefined));
          },
          getUint32: function getUint32(byteOffset) {
            return unpackInt32(get(this, 4, byteOffset, arguments.length > 1 ? arguments[1] : undefined)) >>> 0;
          },
          getFloat32: function getFloat32(byteOffset) {
            return unpackIEEE754(get(this, 4, byteOffset, arguments.length > 1 ? arguments[1] : undefined), 23);
          },
          getFloat64: function getFloat64(byteOffset) {
            return unpackIEEE754(get(this, 8, byteOffset, arguments.length > 1 ? arguments[1] : undefined), 52);
          },
          setInt8: function setInt8(byteOffset, value) {
            set(this, 1, byteOffset, packInt8, value);
          },
          setUint8: function setUint8(byteOffset, value) {
            set(this, 1, byteOffset, packInt8, value);
          },
          setInt16: function setInt16(byteOffset, value) {
            set(this, 2, byteOffset, packInt16, value, arguments.length > 2 ? arguments[2] : undefined);
          },
          setUint16: function setUint16(byteOffset, value) {
            set(this, 2, byteOffset, packInt16, value, arguments.length > 2 ? arguments[2] : undefined);
          },
          setInt32: function setInt32(byteOffset, value) {
            set(this, 4, byteOffset, packInt32, value, arguments.length > 2 ? arguments[2] : undefined);
          },
          setUint32: function setUint32(byteOffset, value) {
            set(this, 4, byteOffset, packInt32, value, arguments.length > 2 ? arguments[2] : undefined);
          },
          setFloat32: function setFloat32(byteOffset, value) {
            set(this, 4, byteOffset, packFloat32, value, arguments.length > 2 ? arguments[2] : undefined);
          },
          setFloat64: function setFloat64(byteOffset, value) {
            set(this, 8, byteOffset, packFloat64, value, arguments.length > 2 ? arguments[2] : undefined);
          }
        });
      } else {
        if (!fails(function() {
          NativeArrayBuffer(1);
        }) || !fails(function() {
          new NativeArrayBuffer(-1);
        }) || fails(function() {
          new NativeArrayBuffer();
          new NativeArrayBuffer(1.5);
          new NativeArrayBuffer(NaN);
          return NativeArrayBuffer.name != ARRAY_BUFFER;
        })) {
          $ArrayBuffer = function ArrayBuffer(length) {
            anInstance(this, $ArrayBuffer);
            return new NativeArrayBuffer(toIndex(length));
          };
          var ArrayBufferPrototype = $ArrayBuffer[PROTOTYPE] = NativeArrayBuffer[PROTOTYPE];
          for (var keys = getOwnPropertyNames(NativeArrayBuffer), j = 0, key; keys.length > j; ) {
            if (!((key = keys[j++]) in $ArrayBuffer)) {
              createNonEnumerableProperty($ArrayBuffer, key, NativeArrayBuffer[key]);
            }
          }
          ArrayBufferPrototype.constructor = $ArrayBuffer;
        }
        if (setPrototypeOf && getPrototypeOf($DataViewPrototype) !== ObjectPrototype) {
          setPrototypeOf($DataViewPrototype, ObjectPrototype);
        }
        var testView = new $DataView(new $ArrayBuffer(2));
        var nativeSetInt8 = $DataViewPrototype.setInt8;
        testView.setInt8(0, 2147483648);
        testView.setInt8(1, 2147483649);
        if (testView.getInt8(0) || !testView.getInt8(1)) {
          redefineAll($DataViewPrototype, {
            setInt8: function setInt8(byteOffset, value) {
              nativeSetInt8.call(this, byteOffset, value << 24 >> 24);
            },
            setUint8: function setUint8(byteOffset, value) {
              nativeSetInt8.call(this, byteOffset, value << 24 >> 24);
            }
          }, {
            unsafe: true
          });
        }
      }
      setToStringTag($ArrayBuffer, ARRAY_BUFFER);
      setToStringTag($DataView, DATA_VIEW);
      module.exports = {
        ArrayBuffer: $ArrayBuffer,
        DataView: $DataView
      };
    }, {
      '../internals/an-instance': 37,
      '../internals/array-buffer-native': 39,
      '../internals/array-fill': 43,
      '../internals/create-non-enumerable-property': 57,
      '../internals/descriptors': 60,
      '../internals/fails': 64,
      '../internals/global': 68,
      '../internals/ieee754': 73,
      '../internals/internal-state': 77,
      '../internals/object-define-property': 89,
      '../internals/object-get-own-property-names': 91,
      '../internals/object-get-prototype-of': 93,
      '../internals/object-set-prototype-of': 97,
      '../internals/redefine-all': 101,
      '../internals/set-to-string-tag': 106,
      '../internals/to-index': 112,
      '../internals/to-integer': 114,
      '../internals/to-length': 115
    } ],
    42: [ function(_dereq_, module, exports) {
      'use strict';
      var toObject = _dereq_('../internals/to-object');
      var toAbsoluteIndex = _dereq_('../internals/to-absolute-index');
      var toLength = _dereq_('../internals/to-length');
      var min = Math.min;
      module.exports = [].copyWithin || function copyWithin(target, start) {
        var O = toObject(this);
        var len = toLength(O.length);
        var to = toAbsoluteIndex(target, len);
        var from = toAbsoluteIndex(start, len);
        var end = arguments.length > 2 ? arguments[2] : undefined;
        var count = min((end === undefined ? len : toAbsoluteIndex(end, len)) - from, len - to);
        var inc = 1;
        if (from < to && to < from + count) {
          inc = -1;
          from += count - 1;
          to += count - 1;
        }
        while (count-- > 0) {
          if (from in O) {
            O[to] = O[from];
          } else {
            delete O[to];
          }
          to += inc;
          from += inc;
        }
        return O;
      };
    }, {
      '../internals/to-absolute-index': 111,
      '../internals/to-length': 115,
      '../internals/to-object': 116
    } ],
    43: [ function(_dereq_, module, exports) {
      'use strict';
      var toObject = _dereq_('../internals/to-object');
      var toAbsoluteIndex = _dereq_('../internals/to-absolute-index');
      var toLength = _dereq_('../internals/to-length');
      module.exports = function fill(value) {
        var O = toObject(this);
        var length = toLength(O.length);
        var argumentsLength = arguments.length;
        var index = toAbsoluteIndex(argumentsLength > 1 ? arguments[1] : undefined, length);
        var end = argumentsLength > 2 ? arguments[2] : undefined;
        var endPos = end === undefined ? length : toAbsoluteIndex(end, length);
        while (endPos > index) {
          O[index++] = value;
        }
        return O;
      };
    }, {
      '../internals/to-absolute-index': 111,
      '../internals/to-length': 115,
      '../internals/to-object': 116
    } ],
    44: [ function(_dereq_, module, exports) {
      var toIndexedObject = _dereq_('../internals/to-indexed-object');
      var toLength = _dereq_('../internals/to-length');
      var toAbsoluteIndex = _dereq_('../internals/to-absolute-index');
      var createMethod = function(IS_INCLUDES) {
        return function($this, el, fromIndex) {
          var O = toIndexedObject($this);
          var length = toLength(O.length);
          var index = toAbsoluteIndex(fromIndex, length);
          var value;
          if (IS_INCLUDES && el != el) {
            while (length > index) {
              value = O[index++];
              if (value != value) {
                return true;
              }
            }
          } else {
            for (;length > index; index++) {
              if ((IS_INCLUDES || index in O) && O[index] === el) {
                return IS_INCLUDES || index || 0;
              }
            }
          }
          return !IS_INCLUDES && -1;
        };
      };
      module.exports = {
        includes: createMethod(true),
        indexOf: createMethod(false)
      };
    }, {
      '../internals/to-absolute-index': 111,
      '../internals/to-indexed-object': 113,
      '../internals/to-length': 115
    } ],
    45: [ function(_dereq_, module, exports) {
      var bind = _dereq_('../internals/function-bind-context');
      var IndexedObject = _dereq_('../internals/indexed-object');
      var toObject = _dereq_('../internals/to-object');
      var toLength = _dereq_('../internals/to-length');
      var arraySpeciesCreate = _dereq_('../internals/array-species-create');
      var push = [].push;
      var createMethod = function(TYPE) {
        var IS_MAP = TYPE == 1;
        var IS_FILTER = TYPE == 2;
        var IS_SOME = TYPE == 3;
        var IS_EVERY = TYPE == 4;
        var IS_FIND_INDEX = TYPE == 6;
        var NO_HOLES = TYPE == 5 || IS_FIND_INDEX;
        return function($this, callbackfn, that, specificCreate) {
          var O = toObject($this);
          var self = IndexedObject(O);
          var boundFunction = bind(callbackfn, that, 3);
          var length = toLength(self.length);
          var index = 0;
          var create = specificCreate || arraySpeciesCreate;
          var target = IS_MAP ? create($this, length) : IS_FILTER ? create($this, 0) : undefined;
          var value, result;
          for (;length > index; index++) {
            if (NO_HOLES || index in self) {
              value = self[index];
              result = boundFunction(value, index, O);
              if (TYPE) {
                if (IS_MAP) {
                  target[index] = result;
                } else if (result) {
                  switch (TYPE) {
                   case 3:
                    return true;

                   case 5:
                    return value;

                   case 6:
                    return index;

                   case 2:
                    push.call(target, value);
                  }
                } else if (IS_EVERY) {
                  return false;
                }
              }
            }
          }
          return IS_FIND_INDEX ? -1 : IS_SOME || IS_EVERY ? IS_EVERY : target;
        };
      };
      module.exports = {
        forEach: createMethod(0),
        map: createMethod(1),
        filter: createMethod(2),
        some: createMethod(3),
        every: createMethod(4),
        find: createMethod(5),
        findIndex: createMethod(6)
      };
    }, {
      '../internals/array-species-create': 50,
      '../internals/function-bind-context': 65,
      '../internals/indexed-object': 74,
      '../internals/to-length': 115,
      '../internals/to-object': 116
    } ],
    46: [ function(_dereq_, module, exports) {
      'use strict';
      var toIndexedObject = _dereq_('../internals/to-indexed-object');
      var toInteger = _dereq_('../internals/to-integer');
      var toLength = _dereq_('../internals/to-length');
      var arrayMethodIsStrict = _dereq_('../internals/array-method-is-strict');
      var arrayMethodUsesToLength = _dereq_('../internals/array-method-uses-to-length');
      var min = Math.min;
      var nativeLastIndexOf = [].lastIndexOf;
      var NEGATIVE_ZERO = !!nativeLastIndexOf && 1 / [ 1 ].lastIndexOf(1, -0) < 0;
      var STRICT_METHOD = arrayMethodIsStrict('lastIndexOf');
      var USES_TO_LENGTH = arrayMethodUsesToLength('indexOf', {
        ACCESSORS: true,
        1: 0
      });
      var FORCED = NEGATIVE_ZERO || !STRICT_METHOD || !USES_TO_LENGTH;
      module.exports = FORCED ? function lastIndexOf(searchElement) {
        if (NEGATIVE_ZERO) {
          return nativeLastIndexOf.apply(this, arguments) || 0;
        }
        var O = toIndexedObject(this);
        var length = toLength(O.length);
        var index = length - 1;
        if (arguments.length > 1) {
          index = min(index, toInteger(arguments[1]));
        }
        if (index < 0) {
          index = length + index;
        }
        for (;index >= 0; index--) {
          if (index in O && O[index] === searchElement) {
            return index || 0;
          }
        }
        return -1;
      } : nativeLastIndexOf;
    }, {
      '../internals/array-method-is-strict': 47,
      '../internals/array-method-uses-to-length': 48,
      '../internals/to-indexed-object': 113,
      '../internals/to-integer': 114,
      '../internals/to-length': 115
    } ],
    47: [ function(_dereq_, module, exports) {
      'use strict';
      var fails = _dereq_('../internals/fails');
      module.exports = function(METHOD_NAME, argument) {
        var method = [][METHOD_NAME];
        return !!method && fails(function() {
          method.call(null, argument || function() {
            throw 1;
          }, 1);
        });
      };
    }, {
      '../internals/fails': 64
    } ],
    48: [ function(_dereq_, module, exports) {
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var fails = _dereq_('../internals/fails');
      var has = _dereq_('../internals/has');
      var defineProperty = Object.defineProperty;
      var cache = {};
      var thrower = function(it) {
        throw it;
      };
      module.exports = function(METHOD_NAME, options) {
        if (has(cache, METHOD_NAME)) {
          return cache[METHOD_NAME];
        }
        if (!options) {
          options = {};
        }
        var method = [][METHOD_NAME];
        var ACCESSORS = has(options, 'ACCESSORS') ? options.ACCESSORS : false;
        var argument0 = has(options, 0) ? options[0] : thrower;
        var argument1 = has(options, 1) ? options[1] : undefined;
        return cache[METHOD_NAME] = !!method && !fails(function() {
          if (ACCESSORS && !DESCRIPTORS) {
            return true;
          }
          var O = {
            length: -1
          };
          if (ACCESSORS) {
            defineProperty(O, 1, {
              enumerable: true,
              get: thrower
            });
          } else {
            O[1] = 1;
          }
          method.call(O, argument0, argument1);
        });
      };
    }, {
      '../internals/descriptors': 60,
      '../internals/fails': 64,
      '../internals/has': 69
    } ],
    49: [ function(_dereq_, module, exports) {
      var aFunction = _dereq_('../internals/a-function');
      var toObject = _dereq_('../internals/to-object');
      var IndexedObject = _dereq_('../internals/indexed-object');
      var toLength = _dereq_('../internals/to-length');
      var createMethod = function(IS_RIGHT) {
        return function(that, callbackfn, argumentsLength, memo) {
          aFunction(callbackfn);
          var O = toObject(that);
          var self = IndexedObject(O);
          var length = toLength(O.length);
          var index = IS_RIGHT ? length - 1 : 0;
          var i = IS_RIGHT ? -1 : 1;
          if (argumentsLength < 2) {
            while (true) {
              if (index in self) {
                memo = self[index];
                index += i;
                break;
              }
              index += i;
              if (IS_RIGHT ? index < 0 : length <= index) {
                throw TypeError('Reduce of empty array with no initial value');
              }
            }
          }
          for (;IS_RIGHT ? index >= 0 : length > index; index += i) {
            if (index in self) {
              memo = callbackfn(memo, self[index], index, O);
            }
          }
          return memo;
        };
      };
      module.exports = {
        left: createMethod(false),
        right: createMethod(true)
      };
    }, {
      '../internals/a-function': 34,
      '../internals/indexed-object': 74,
      '../internals/to-length': 115,
      '../internals/to-object': 116
    } ],
    50: [ function(_dereq_, module, exports) {
      var isObject = _dereq_('../internals/is-object');
      var isArray = _dereq_('../internals/is-array');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var SPECIES = wellKnownSymbol('species');
      module.exports = function(originalArray, length) {
        var C;
        if (isArray(originalArray)) {
          C = originalArray.constructor;
          if (typeof C == 'function' && (C === Array || isArray(C.prototype))) {
            C = undefined;
          } else if (isObject(C)) {
            C = C[SPECIES];
            if (C === null) {
              C = undefined;
            }
          }
        }
        return new (C === undefined ? Array : C)(length === 0 ? 0 : length);
      };
    }, {
      '../internals/is-array': 79,
      '../internals/is-object': 81,
      '../internals/well-known-symbol': 126
    } ],
    51: [ function(_dereq_, module, exports) {
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var ITERATOR = wellKnownSymbol('iterator');
      var SAFE_CLOSING = false;
      try {
        var called = 0;
        var iteratorWithReturn = {
          next: function() {
            return {
              done: !!called++
            };
          },
          return: function() {
            SAFE_CLOSING = true;
          }
        };
        iteratorWithReturn[ITERATOR] = function() {
          return this;
        };
        Array.from(iteratorWithReturn, function() {
          throw 2;
        });
      } catch (error) {}
      module.exports = function(exec, SKIP_CLOSING) {
        if (!SKIP_CLOSING && !SAFE_CLOSING) {
          return false;
        }
        var ITERATION_SUPPORT = false;
        try {
          var object = {};
          object[ITERATOR] = function() {
            return {
              next: function() {
                return {
                  done: ITERATION_SUPPORT = true
                };
              }
            };
          };
          exec(object);
        } catch (error) {}
        return ITERATION_SUPPORT;
      };
    }, {
      '../internals/well-known-symbol': 126
    } ],
    52: [ function(_dereq_, module, exports) {
      var toString = {}.toString;
      module.exports = function(it) {
        return toString.call(it).slice(8, -1);
      };
    }, {} ],
    53: [ function(_dereq_, module, exports) {
      var TO_STRING_TAG_SUPPORT = _dereq_('../internals/to-string-tag-support');
      var classofRaw = _dereq_('../internals/classof-raw');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var TO_STRING_TAG = wellKnownSymbol('toStringTag');
      var CORRECT_ARGUMENTS = classofRaw(function() {
        return arguments;
      }()) == 'Arguments';
      var tryGet = function(it, key) {
        try {
          return it[key];
        } catch (error) {}
      };
      module.exports = TO_STRING_TAG_SUPPORT ? classofRaw : function(it) {
        var O, tag, result;
        return it === undefined ? 'Undefined' : it === null ? 'Null' : typeof (tag = tryGet(O = Object(it), TO_STRING_TAG)) == 'string' ? tag : CORRECT_ARGUMENTS ? classofRaw(O) : (result = classofRaw(O)) == 'Object' && typeof O.callee == 'function' ? 'Arguments' : result;
      };
    }, {
      '../internals/classof-raw': 52,
      '../internals/to-string-tag-support': 120,
      '../internals/well-known-symbol': 126
    } ],
    54: [ function(_dereq_, module, exports) {
      var has = _dereq_('../internals/has');
      var ownKeys = _dereq_('../internals/own-keys');
      var getOwnPropertyDescriptorModule = _dereq_('../internals/object-get-own-property-descriptor');
      var definePropertyModule = _dereq_('../internals/object-define-property');
      module.exports = function(target, source) {
        var keys = ownKeys(source);
        var defineProperty = definePropertyModule.f;
        var getOwnPropertyDescriptor = getOwnPropertyDescriptorModule.f;
        for (var i = 0; i < keys.length; i++) {
          var key = keys[i];
          if (!has(target, key)) {
            defineProperty(target, key, getOwnPropertyDescriptor(source, key));
          }
        }
      };
    }, {
      '../internals/has': 69,
      '../internals/object-define-property': 89,
      '../internals/object-get-own-property-descriptor': 90,
      '../internals/own-keys': 99
    } ],
    55: [ function(_dereq_, module, exports) {
      var fails = _dereq_('../internals/fails');
      module.exports = !fails(function() {
        function F() {}
        F.prototype.constructor = null;
        return Object.getPrototypeOf(new F()) !== F.prototype;
      });
    }, {
      '../internals/fails': 64
    } ],
    56: [ function(_dereq_, module, exports) {
      'use strict';
      var IteratorPrototype = _dereq_('../internals/iterators-core').IteratorPrototype;
      var create = _dereq_('../internals/object-create');
      var createPropertyDescriptor = _dereq_('../internals/create-property-descriptor');
      var setToStringTag = _dereq_('../internals/set-to-string-tag');
      var Iterators = _dereq_('../internals/iterators');
      var returnThis = function() {
        return this;
      };
      module.exports = function(IteratorConstructor, NAME, next) {
        var TO_STRING_TAG = NAME + ' Iterator';
        IteratorConstructor.prototype = create(IteratorPrototype, {
          next: createPropertyDescriptor(1, next)
        });
        setToStringTag(IteratorConstructor, TO_STRING_TAG, false, true);
        Iterators[TO_STRING_TAG] = returnThis;
        return IteratorConstructor;
      };
    }, {
      '../internals/create-property-descriptor': 58,
      '../internals/iterators': 84,
      '../internals/iterators-core': 83,
      '../internals/object-create': 87,
      '../internals/set-to-string-tag': 106
    } ],
    57: [ function(_dereq_, module, exports) {
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var definePropertyModule = _dereq_('../internals/object-define-property');
      var createPropertyDescriptor = _dereq_('../internals/create-property-descriptor');
      module.exports = DESCRIPTORS ? function(object, key, value) {
        return definePropertyModule.f(object, key, createPropertyDescriptor(1, value));
      } : function(object, key, value) {
        object[key] = value;
        return object;
      };
    }, {
      '../internals/create-property-descriptor': 58,
      '../internals/descriptors': 60,
      '../internals/object-define-property': 89
    } ],
    58: [ function(_dereq_, module, exports) {
      module.exports = function(bitmap, value) {
        return {
          enumerable: !(bitmap & 1),
          configurable: !(bitmap & 2),
          writable: !(bitmap & 4),
          value: value
        };
      };
    }, {} ],
    59: [ function(_dereq_, module, exports) {
      'use strict';
      var $ = _dereq_('../internals/export');
      var createIteratorConstructor = _dereq_('../internals/create-iterator-constructor');
      var getPrototypeOf = _dereq_('../internals/object-get-prototype-of');
      var setPrototypeOf = _dereq_('../internals/object-set-prototype-of');
      var setToStringTag = _dereq_('../internals/set-to-string-tag');
      var createNonEnumerableProperty = _dereq_('../internals/create-non-enumerable-property');
      var redefine = _dereq_('../internals/redefine');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var IS_PURE = _dereq_('../internals/is-pure');
      var Iterators = _dereq_('../internals/iterators');
      var IteratorsCore = _dereq_('../internals/iterators-core');
      var IteratorPrototype = IteratorsCore.IteratorPrototype;
      var BUGGY_SAFARI_ITERATORS = IteratorsCore.BUGGY_SAFARI_ITERATORS;
      var ITERATOR = wellKnownSymbol('iterator');
      var KEYS = 'keys';
      var VALUES = 'values';
      var ENTRIES = 'entries';
      var returnThis = function() {
        return this;
      };
      module.exports = function(Iterable, NAME, IteratorConstructor, next, DEFAULT, IS_SET, FORCED) {
        createIteratorConstructor(IteratorConstructor, NAME, next);
        var getIterationMethod = function(KIND) {
          if (KIND === DEFAULT && defaultIterator) {
            return defaultIterator;
          }
          if (!BUGGY_SAFARI_ITERATORS && KIND in IterablePrototype) {
            return IterablePrototype[KIND];
          }
          switch (KIND) {
           case KEYS:
            return function keys() {
              return new IteratorConstructor(this, KIND);
            };

           case VALUES:
            return function values() {
              return new IteratorConstructor(this, KIND);
            };

           case ENTRIES:
            return function entries() {
              return new IteratorConstructor(this, KIND);
            };
          }
          return function() {
            return new IteratorConstructor(this);
          };
        };
        var TO_STRING_TAG = NAME + ' Iterator';
        var INCORRECT_VALUES_NAME = false;
        var IterablePrototype = Iterable.prototype;
        var nativeIterator = IterablePrototype[ITERATOR] || IterablePrototype['@@iterator'] || DEFAULT && IterablePrototype[DEFAULT];
        var defaultIterator = !BUGGY_SAFARI_ITERATORS && nativeIterator || getIterationMethod(DEFAULT);
        var anyNativeIterator = NAME == 'Array' ? IterablePrototype.entries || nativeIterator : nativeIterator;
        var CurrentIteratorPrototype, methods, KEY;
        if (anyNativeIterator) {
          CurrentIteratorPrototype = getPrototypeOf(anyNativeIterator.call(new Iterable()));
          if (IteratorPrototype !== Object.prototype && CurrentIteratorPrototype.next) {
            if (!IS_PURE && getPrototypeOf(CurrentIteratorPrototype) !== IteratorPrototype) {
              if (setPrototypeOf) {
                setPrototypeOf(CurrentIteratorPrototype, IteratorPrototype);
              } else if (typeof CurrentIteratorPrototype[ITERATOR] != 'function') {
                createNonEnumerableProperty(CurrentIteratorPrototype, ITERATOR, returnThis);
              }
            }
            setToStringTag(CurrentIteratorPrototype, TO_STRING_TAG, true, true);
            if (IS_PURE) {
              Iterators[TO_STRING_TAG] = returnThis;
            }
          }
        }
        if (DEFAULT == VALUES && nativeIterator && nativeIterator.name !== VALUES) {
          INCORRECT_VALUES_NAME = true;
          defaultIterator = function values() {
            return nativeIterator.call(this);
          };
        }
        if ((!IS_PURE || FORCED) && IterablePrototype[ITERATOR] !== defaultIterator) {
          createNonEnumerableProperty(IterablePrototype, ITERATOR, defaultIterator);
        }
        Iterators[NAME] = defaultIterator;
        if (DEFAULT) {
          methods = {
            values: getIterationMethod(VALUES),
            keys: IS_SET ? defaultIterator : getIterationMethod(KEYS),
            entries: getIterationMethod(ENTRIES)
          };
          if (FORCED) {
            for (KEY in methods) {
              if (BUGGY_SAFARI_ITERATORS || INCORRECT_VALUES_NAME || !(KEY in IterablePrototype)) {
                redefine(IterablePrototype, KEY, methods[KEY]);
              }
            }
          } else {
            $({
              target: NAME,
              proto: true,
              forced: BUGGY_SAFARI_ITERATORS || INCORRECT_VALUES_NAME
            }, methods);
          }
        }
        return methods;
      };
    }, {
      '../internals/create-iterator-constructor': 56,
      '../internals/create-non-enumerable-property': 57,
      '../internals/export': 63,
      '../internals/is-pure': 82,
      '../internals/iterators': 84,
      '../internals/iterators-core': 83,
      '../internals/object-get-prototype-of': 93,
      '../internals/object-set-prototype-of': 97,
      '../internals/redefine': 102,
      '../internals/set-to-string-tag': 106,
      '../internals/well-known-symbol': 126
    } ],
    60: [ function(_dereq_, module, exports) {
      var fails = _dereq_('../internals/fails');
      module.exports = !fails(function() {
        return Object.defineProperty({}, 1, {
          get: function() {
            return 7;
          }
        })[1] != 7;
      });
    }, {
      '../internals/fails': 64
    } ],
    61: [ function(_dereq_, module, exports) {
      var global = _dereq_('../internals/global');
      var isObject = _dereq_('../internals/is-object');
      var document = global.document;
      var EXISTS = isObject(document) && isObject(document.createElement);
      module.exports = function(it) {
        return EXISTS ? document.createElement(it) : {};
      };
    }, {
      '../internals/global': 68,
      '../internals/is-object': 81
    } ],
    62: [ function(_dereq_, module, exports) {
      module.exports = [ 'constructor', 'hasOwnProperty', 'isPrototypeOf', 'propertyIsEnumerable', 'toLocaleString', 'toString', 'valueOf' ];
    }, {} ],
    63: [ function(_dereq_, module, exports) {
      var global = _dereq_('../internals/global');
      var getOwnPropertyDescriptor = _dereq_('../internals/object-get-own-property-descriptor').f;
      var createNonEnumerableProperty = _dereq_('../internals/create-non-enumerable-property');
      var redefine = _dereq_('../internals/redefine');
      var setGlobal = _dereq_('../internals/set-global');
      var copyConstructorProperties = _dereq_('../internals/copy-constructor-properties');
      var isForced = _dereq_('../internals/is-forced');
      module.exports = function(options, source) {
        var TARGET = options.target;
        var GLOBAL = options.global;
        var STATIC = options.stat;
        var FORCED, target, key, targetProperty, sourceProperty, descriptor;
        if (GLOBAL) {
          target = global;
        } else if (STATIC) {
          target = global[TARGET] || setGlobal(TARGET, {});
        } else {
          target = (global[TARGET] || {}).prototype;
        }
        if (target) {
          for (key in source) {
            sourceProperty = source[key];
            if (options.noTargetGet) {
              descriptor = getOwnPropertyDescriptor(target, key);
              targetProperty = descriptor && descriptor.value;
            } else {
              targetProperty = target[key];
            }
            FORCED = isForced(GLOBAL ? key : TARGET + (STATIC ? '.' : '#') + key, options.forced);
            if (!FORCED && targetProperty !== undefined) {
              if (typeof sourceProperty === typeof targetProperty) {
                continue;
              }
              copyConstructorProperties(sourceProperty, targetProperty);
            }
            if (options.sham || targetProperty && targetProperty.sham) {
              createNonEnumerableProperty(sourceProperty, 'sham', true);
            }
            redefine(target, key, sourceProperty, options);
          }
        }
      };
    }, {
      '../internals/copy-constructor-properties': 54,
      '../internals/create-non-enumerable-property': 57,
      '../internals/global': 68,
      '../internals/is-forced': 80,
      '../internals/object-get-own-property-descriptor': 90,
      '../internals/redefine': 102,
      '../internals/set-global': 104
    } ],
    64: [ function(_dereq_, module, exports) {
      module.exports = function(exec) {
        try {
          return !!exec();
        } catch (error) {
          return true;
        }
      };
    }, {} ],
    65: [ function(_dereq_, module, exports) {
      var aFunction = _dereq_('../internals/a-function');
      module.exports = function(fn, that, length) {
        aFunction(fn);
        if (that === undefined) {
          return fn;
        }
        switch (length) {
         case 0:
          return function() {
            return fn.call(that);
          };

         case 1:
          return function(a) {
            return fn.call(that, a);
          };

         case 2:
          return function(a, b) {
            return fn.call(that, a, b);
          };

         case 3:
          return function(a, b, c) {
            return fn.call(that, a, b, c);
          };
        }
        return function() {
          return fn.apply(that, arguments);
        };
      };
    }, {
      '../internals/a-function': 34
    } ],
    66: [ function(_dereq_, module, exports) {
      var path = _dereq_('../internals/path');
      var global = _dereq_('../internals/global');
      var aFunction = function(variable) {
        return typeof variable == 'function' ? variable : undefined;
      };
      module.exports = function(namespace, method) {
        return arguments.length < 2 ? aFunction(path[namespace]) || aFunction(global[namespace]) : path[namespace] && path[namespace][method] || global[namespace] && global[namespace][method];
      };
    }, {
      '../internals/global': 68,
      '../internals/path': 100
    } ],
    67: [ function(_dereq_, module, exports) {
      var classof = _dereq_('../internals/classof');
      var Iterators = _dereq_('../internals/iterators');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var ITERATOR = wellKnownSymbol('iterator');
      module.exports = function(it) {
        if (it != undefined) {
          return it[ITERATOR] || it['@@iterator'] || Iterators[classof(it)];
        }
      };
    }, {
      '../internals/classof': 53,
      '../internals/iterators': 84,
      '../internals/well-known-symbol': 126
    } ],
    68: [ function(_dereq_, module, exports) {
      (function(global) {
        var check = function(it) {
          return it && it.Math == Math && it;
        };
        module.exports = check(typeof globalThis == 'object' && globalThis) || check(typeof window == 'object' && window) || check(typeof self == 'object' && self) || check(typeof global == 'object' && global) || Function('return this')();
      }).call(this, typeof global !== 'undefined' ? global : typeof self !== 'undefined' ? self : typeof window !== 'undefined' ? window : {});
    }, {} ],
    69: [ function(_dereq_, module, exports) {
      var hasOwnProperty = {}.hasOwnProperty;
      module.exports = function(it, key) {
        return hasOwnProperty.call(it, key);
      };
    }, {} ],
    70: [ function(_dereq_, module, exports) {
      module.exports = {};
    }, {} ],
    71: [ function(_dereq_, module, exports) {
      var getBuiltIn = _dereq_('../internals/get-built-in');
      module.exports = getBuiltIn('document', 'documentElement');
    }, {
      '../internals/get-built-in': 66
    } ],
    72: [ function(_dereq_, module, exports) {
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var fails = _dereq_('../internals/fails');
      var createElement = _dereq_('../internals/document-create-element');
      module.exports = !DESCRIPTORS && !fails(function() {
        return Object.defineProperty(createElement('div'), 'a', {
          get: function() {
            return 7;
          }
        }).a != 7;
      });
    }, {
      '../internals/descriptors': 60,
      '../internals/document-create-element': 61,
      '../internals/fails': 64
    } ],
    73: [ function(_dereq_, module, exports) {
      var Infinity = 1 / 0;
      var abs = Math.abs;
      var pow = Math.pow;
      var floor = Math.floor;
      var log = Math.log;
      var LN2 = Math.LN2;
      var pack = function(number, mantissaLength, bytes) {
        var buffer = new Array(bytes);
        var exponentLength = bytes * 8 - mantissaLength - 1;
        var eMax = (1 << exponentLength) - 1;
        var eBias = eMax >> 1;
        var rt = mantissaLength === 23 ? pow(2, -24) - pow(2, -77) : 0;
        var sign = number < 0 || number === 0 && 1 / number < 0 ? 1 : 0;
        var index = 0;
        var exponent, mantissa, c;
        number = abs(number);
        if (number != number || number === Infinity) {
          mantissa = number != number ? 1 : 0;
          exponent = eMax;
        } else {
          exponent = floor(log(number) / LN2);
          if (number * (c = pow(2, -exponent)) < 1) {
            exponent--;
            c *= 2;
          }
          if (exponent + eBias >= 1) {
            number += rt / c;
          } else {
            number += rt * pow(2, 1 - eBias);
          }
          if (number * c >= 2) {
            exponent++;
            c /= 2;
          }
          if (exponent + eBias >= eMax) {
            mantissa = 0;
            exponent = eMax;
          } else if (exponent + eBias >= 1) {
            mantissa = (number * c - 1) * pow(2, mantissaLength);
            exponent = exponent + eBias;
          } else {
            mantissa = number * pow(2, eBias - 1) * pow(2, mantissaLength);
            exponent = 0;
          }
        }
        for (;mantissaLength >= 8; buffer[index++] = mantissa & 255, mantissa /= 256, mantissaLength -= 8) {}
        exponent = exponent << mantissaLength | mantissa;
        exponentLength += mantissaLength;
        for (;exponentLength > 0; buffer[index++] = exponent & 255, exponent /= 256, exponentLength -= 8) {}
        buffer[--index] |= sign * 128;
        return buffer;
      };
      var unpack = function(buffer, mantissaLength) {
        var bytes = buffer.length;
        var exponentLength = bytes * 8 - mantissaLength - 1;
        var eMax = (1 << exponentLength) - 1;
        var eBias = eMax >> 1;
        var nBits = exponentLength - 7;
        var index = bytes - 1;
        var sign = buffer[index--];
        var exponent = sign & 127;
        var mantissa;
        sign >>= 7;
        for (;nBits > 0; exponent = exponent * 256 + buffer[index], index--, nBits -= 8) {}
        mantissa = exponent & (1 << -nBits) - 1;
        exponent >>= -nBits;
        nBits += mantissaLength;
        for (;nBits > 0; mantissa = mantissa * 256 + buffer[index], index--, nBits -= 8) {}
        if (exponent === 0) {
          exponent = 1 - eBias;
        } else if (exponent === eMax) {
          return mantissa ? NaN : sign ? -Infinity : Infinity;
        } else {
          mantissa = mantissa + pow(2, mantissaLength);
          exponent = exponent - eBias;
        }
        return (sign ? -1 : 1) * mantissa * pow(2, exponent - mantissaLength);
      };
      module.exports = {
        pack: pack,
        unpack: unpack
      };
    }, {} ],
    74: [ function(_dereq_, module, exports) {
      var fails = _dereq_('../internals/fails');
      var classof = _dereq_('../internals/classof-raw');
      var split = ''.split;
      module.exports = fails(function() {
        return !Object('z').propertyIsEnumerable(0);
      }) ? function(it) {
        return classof(it) == 'String' ? split.call(it, '') : Object(it);
      } : Object;
    }, {
      '../internals/classof-raw': 52,
      '../internals/fails': 64
    } ],
    75: [ function(_dereq_, module, exports) {
      var isObject = _dereq_('../internals/is-object');
      var setPrototypeOf = _dereq_('../internals/object-set-prototype-of');
      module.exports = function($this, dummy, Wrapper) {
        var NewTarget, NewTargetPrototype;
        if (setPrototypeOf && typeof (NewTarget = dummy.constructor) == 'function' && NewTarget !== Wrapper && isObject(NewTargetPrototype = NewTarget.prototype) && NewTargetPrototype !== Wrapper.prototype) {
          setPrototypeOf($this, NewTargetPrototype);
        }
        return $this;
      };
    }, {
      '../internals/is-object': 81,
      '../internals/object-set-prototype-of': 97
    } ],
    76: [ function(_dereq_, module, exports) {
      var store = _dereq_('../internals/shared-store');
      var functionToString = Function.toString;
      if (typeof store.inspectSource != 'function') {
        store.inspectSource = function(it) {
          return functionToString.call(it);
        };
      }
      module.exports = store.inspectSource;
    }, {
      '../internals/shared-store': 108
    } ],
    77: [ function(_dereq_, module, exports) {
      var NATIVE_WEAK_MAP = _dereq_('../internals/native-weak-map');
      var global = _dereq_('../internals/global');
      var isObject = _dereq_('../internals/is-object');
      var createNonEnumerableProperty = _dereq_('../internals/create-non-enumerable-property');
      var objectHas = _dereq_('../internals/has');
      var sharedKey = _dereq_('../internals/shared-key');
      var hiddenKeys = _dereq_('../internals/hidden-keys');
      var WeakMap = global.WeakMap;
      var set, get, has;
      var enforce = function(it) {
        return has(it) ? get(it) : set(it, {});
      };
      var getterFor = function(TYPE) {
        return function(it) {
          var state;
          if (!isObject(it) || (state = get(it)).type !== TYPE) {
            throw TypeError('Incompatible receiver, ' + TYPE + ' required');
          }
          return state;
        };
      };
      if (NATIVE_WEAK_MAP) {
        var store = new WeakMap();
        var wmget = store.get;
        var wmhas = store.has;
        var wmset = store.set;
        set = function(it, metadata) {
          wmset.call(store, it, metadata);
          return metadata;
        };
        get = function(it) {
          return wmget.call(store, it) || {};
        };
        has = function(it) {
          return wmhas.call(store, it);
        };
      } else {
        var STATE = sharedKey('state');
        hiddenKeys[STATE] = true;
        set = function(it, metadata) {
          createNonEnumerableProperty(it, STATE, metadata);
          return metadata;
        };
        get = function(it) {
          return objectHas(it, STATE) ? it[STATE] : {};
        };
        has = function(it) {
          return objectHas(it, STATE);
        };
      }
      module.exports = {
        set: set,
        get: get,
        has: has,
        enforce: enforce,
        getterFor: getterFor
      };
    }, {
      '../internals/create-non-enumerable-property': 57,
      '../internals/global': 68,
      '../internals/has': 69,
      '../internals/hidden-keys': 70,
      '../internals/is-object': 81,
      '../internals/native-weak-map': 86,
      '../internals/shared-key': 107
    } ],
    78: [ function(_dereq_, module, exports) {
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var Iterators = _dereq_('../internals/iterators');
      var ITERATOR = wellKnownSymbol('iterator');
      var ArrayPrototype = Array.prototype;
      module.exports = function(it) {
        return it !== undefined && (Iterators.Array === it || ArrayPrototype[ITERATOR] === it);
      };
    }, {
      '../internals/iterators': 84,
      '../internals/well-known-symbol': 126
    } ],
    79: [ function(_dereq_, module, exports) {
      var classof = _dereq_('../internals/classof-raw');
      module.exports = Array.isArray || function isArray(arg) {
        return classof(arg) == 'Array';
      };
    }, {
      '../internals/classof-raw': 52
    } ],
    80: [ function(_dereq_, module, exports) {
      var fails = _dereq_('../internals/fails');
      var replacement = /#|\.prototype\./;
      var isForced = function(feature, detection) {
        var value = data[normalize(feature)];
        return value == POLYFILL ? true : value == NATIVE ? false : typeof detection == 'function' ? fails(detection) : !!detection;
      };
      var normalize = isForced.normalize = function(string) {
        return String(string).replace(replacement, '.').toLowerCase();
      };
      var data = isForced.data = {};
      var NATIVE = isForced.NATIVE = 'N';
      var POLYFILL = isForced.POLYFILL = 'P';
      module.exports = isForced;
    }, {
      '../internals/fails': 64
    } ],
    81: [ function(_dereq_, module, exports) {
      module.exports = function(it) {
        return typeof it === 'object' ? it !== null : typeof it === 'function';
      };
    }, {} ],
    82: [ function(_dereq_, module, exports) {
      module.exports = false;
    }, {} ],
    83: [ function(_dereq_, module, exports) {
      'use strict';
      var getPrototypeOf = _dereq_('../internals/object-get-prototype-of');
      var createNonEnumerableProperty = _dereq_('../internals/create-non-enumerable-property');
      var has = _dereq_('../internals/has');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var IS_PURE = _dereq_('../internals/is-pure');
      var ITERATOR = wellKnownSymbol('iterator');
      var BUGGY_SAFARI_ITERATORS = false;
      var returnThis = function() {
        return this;
      };
      var IteratorPrototype, PrototypeOfArrayIteratorPrototype, arrayIterator;
      if ([].keys) {
        arrayIterator = [].keys();
        if (!('next' in arrayIterator)) {
          BUGGY_SAFARI_ITERATORS = true;
        } else {
          PrototypeOfArrayIteratorPrototype = getPrototypeOf(getPrototypeOf(arrayIterator));
          if (PrototypeOfArrayIteratorPrototype !== Object.prototype) {
            IteratorPrototype = PrototypeOfArrayIteratorPrototype;
          }
        }
      }
      if (IteratorPrototype == undefined) {
        IteratorPrototype = {};
      }
      if (!IS_PURE && !has(IteratorPrototype, ITERATOR)) {
        createNonEnumerableProperty(IteratorPrototype, ITERATOR, returnThis);
      }
      module.exports = {
        IteratorPrototype: IteratorPrototype,
        BUGGY_SAFARI_ITERATORS: BUGGY_SAFARI_ITERATORS
      };
    }, {
      '../internals/create-non-enumerable-property': 57,
      '../internals/has': 69,
      '../internals/is-pure': 82,
      '../internals/object-get-prototype-of': 93,
      '../internals/well-known-symbol': 126
    } ],
    84: [ function(_dereq_, module, exports) {
      arguments[4][70][0].apply(exports, arguments);
    }, {
      dup: 70
    } ],
    85: [ function(_dereq_, module, exports) {
      var fails = _dereq_('../internals/fails');
      module.exports = !!Object.getOwnPropertySymbols && !fails(function() {
        return !String(Symbol());
      });
    }, {
      '../internals/fails': 64
    } ],
    86: [ function(_dereq_, module, exports) {
      var global = _dereq_('../internals/global');
      var inspectSource = _dereq_('../internals/inspect-source');
      var WeakMap = global.WeakMap;
      module.exports = typeof WeakMap === 'function' && /native code/.test(inspectSource(WeakMap));
    }, {
      '../internals/global': 68,
      '../internals/inspect-source': 76
    } ],
    87: [ function(_dereq_, module, exports) {
      var anObject = _dereq_('../internals/an-object');
      var defineProperties = _dereq_('../internals/object-define-properties');
      var enumBugKeys = _dereq_('../internals/enum-bug-keys');
      var hiddenKeys = _dereq_('../internals/hidden-keys');
      var html = _dereq_('../internals/html');
      var documentCreateElement = _dereq_('../internals/document-create-element');
      var sharedKey = _dereq_('../internals/shared-key');
      var GT = '>';
      var LT = '<';
      var PROTOTYPE = 'prototype';
      var SCRIPT = 'script';
      var IE_PROTO = sharedKey('IE_PROTO');
      var EmptyConstructor = function() {};
      var scriptTag = function(content) {
        return LT + SCRIPT + GT + content + LT + '/' + SCRIPT + GT;
      };
      var NullProtoObjectViaActiveX = function(activeXDocument) {
        activeXDocument.write(scriptTag(''));
        activeXDocument.close();
        var temp = activeXDocument.parentWindow.Object;
        activeXDocument = null;
        return temp;
      };
      var NullProtoObjectViaIFrame = function() {
        var iframe = documentCreateElement('iframe');
        var JS = 'java' + SCRIPT + ':';
        var iframeDocument;
        iframe.style.display = 'none';
        html.appendChild(iframe);
        iframe.src = String(JS);
        iframeDocument = iframe.contentWindow.document;
        iframeDocument.open();
        iframeDocument.write(scriptTag('document.F=Object'));
        iframeDocument.close();
        return iframeDocument.F;
      };
      var activeXDocument;
      var NullProtoObject = function() {
        try {
          activeXDocument = document.domain && new ActiveXObject('htmlfile');
        } catch (error) {}
        NullProtoObject = activeXDocument ? NullProtoObjectViaActiveX(activeXDocument) : NullProtoObjectViaIFrame();
        var length = enumBugKeys.length;
        while (length--) {
          delete NullProtoObject[PROTOTYPE][enumBugKeys[length]];
        }
        return NullProtoObject();
      };
      hiddenKeys[IE_PROTO] = true;
      module.exports = Object.create || function create(O, Properties) {
        var result;
        if (O !== null) {
          EmptyConstructor[PROTOTYPE] = anObject(O);
          result = new EmptyConstructor();
          EmptyConstructor[PROTOTYPE] = null;
          result[IE_PROTO] = O;
        } else {
          result = NullProtoObject();
        }
        return Properties === undefined ? result : defineProperties(result, Properties);
      };
    }, {
      '../internals/an-object': 38,
      '../internals/document-create-element': 61,
      '../internals/enum-bug-keys': 62,
      '../internals/hidden-keys': 70,
      '../internals/html': 71,
      '../internals/object-define-properties': 88,
      '../internals/shared-key': 107
    } ],
    88: [ function(_dereq_, module, exports) {
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var definePropertyModule = _dereq_('../internals/object-define-property');
      var anObject = _dereq_('../internals/an-object');
      var objectKeys = _dereq_('../internals/object-keys');
      module.exports = DESCRIPTORS ? Object.defineProperties : function defineProperties(O, Properties) {
        anObject(O);
        var keys = objectKeys(Properties);
        var length = keys.length;
        var index = 0;
        var key;
        while (length > index) {
          definePropertyModule.f(O, key = keys[index++], Properties[key]);
        }
        return O;
      };
    }, {
      '../internals/an-object': 38,
      '../internals/descriptors': 60,
      '../internals/object-define-property': 89,
      '../internals/object-keys': 95
    } ],
    89: [ function(_dereq_, module, exports) {
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var IE8_DOM_DEFINE = _dereq_('../internals/ie8-dom-define');
      var anObject = _dereq_('../internals/an-object');
      var toPrimitive = _dereq_('../internals/to-primitive');
      var nativeDefineProperty = Object.defineProperty;
      exports.f = DESCRIPTORS ? nativeDefineProperty : function defineProperty(O, P, Attributes) {
        anObject(O);
        P = toPrimitive(P, true);
        anObject(Attributes);
        if (IE8_DOM_DEFINE) {
          try {
            return nativeDefineProperty(O, P, Attributes);
          } catch (error) {}
        }
        if ('get' in Attributes || 'set' in Attributes) {
          throw TypeError('Accessors not supported');
        }
        if ('value' in Attributes) {
          O[P] = Attributes.value;
        }
        return O;
      };
    }, {
      '../internals/an-object': 38,
      '../internals/descriptors': 60,
      '../internals/ie8-dom-define': 72,
      '../internals/to-primitive': 119
    } ],
    90: [ function(_dereq_, module, exports) {
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var propertyIsEnumerableModule = _dereq_('../internals/object-property-is-enumerable');
      var createPropertyDescriptor = _dereq_('../internals/create-property-descriptor');
      var toIndexedObject = _dereq_('../internals/to-indexed-object');
      var toPrimitive = _dereq_('../internals/to-primitive');
      var has = _dereq_('../internals/has');
      var IE8_DOM_DEFINE = _dereq_('../internals/ie8-dom-define');
      var nativeGetOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
      exports.f = DESCRIPTORS ? nativeGetOwnPropertyDescriptor : function getOwnPropertyDescriptor(O, P) {
        O = toIndexedObject(O);
        P = toPrimitive(P, true);
        if (IE8_DOM_DEFINE) {
          try {
            return nativeGetOwnPropertyDescriptor(O, P);
          } catch (error) {}
        }
        if (has(O, P)) {
          return createPropertyDescriptor(!propertyIsEnumerableModule.f.call(O, P), O[P]);
        }
      };
    }, {
      '../internals/create-property-descriptor': 58,
      '../internals/descriptors': 60,
      '../internals/has': 69,
      '../internals/ie8-dom-define': 72,
      '../internals/object-property-is-enumerable': 96,
      '../internals/to-indexed-object': 113,
      '../internals/to-primitive': 119
    } ],
    91: [ function(_dereq_, module, exports) {
      var internalObjectKeys = _dereq_('../internals/object-keys-internal');
      var enumBugKeys = _dereq_('../internals/enum-bug-keys');
      var hiddenKeys = enumBugKeys.concat('length', 'prototype');
      exports.f = Object.getOwnPropertyNames || function getOwnPropertyNames(O) {
        return internalObjectKeys(O, hiddenKeys);
      };
    }, {
      '../internals/enum-bug-keys': 62,
      '../internals/object-keys-internal': 94
    } ],
    92: [ function(_dereq_, module, exports) {
      exports.f = Object.getOwnPropertySymbols;
    }, {} ],
    93: [ function(_dereq_, module, exports) {
      var has = _dereq_('../internals/has');
      var toObject = _dereq_('../internals/to-object');
      var sharedKey = _dereq_('../internals/shared-key');
      var CORRECT_PROTOTYPE_GETTER = _dereq_('../internals/correct-prototype-getter');
      var IE_PROTO = sharedKey('IE_PROTO');
      var ObjectPrototype = Object.prototype;
      module.exports = CORRECT_PROTOTYPE_GETTER ? Object.getPrototypeOf : function(O) {
        O = toObject(O);
        if (has(O, IE_PROTO)) {
          return O[IE_PROTO];
        }
        if (typeof O.constructor == 'function' && O instanceof O.constructor) {
          return O.constructor.prototype;
        }
        return O instanceof Object ? ObjectPrototype : null;
      };
    }, {
      '../internals/correct-prototype-getter': 55,
      '../internals/has': 69,
      '../internals/shared-key': 107,
      '../internals/to-object': 116
    } ],
    94: [ function(_dereq_, module, exports) {
      var has = _dereq_('../internals/has');
      var toIndexedObject = _dereq_('../internals/to-indexed-object');
      var indexOf = _dereq_('../internals/array-includes').indexOf;
      var hiddenKeys = _dereq_('../internals/hidden-keys');
      module.exports = function(object, names) {
        var O = toIndexedObject(object);
        var i = 0;
        var result = [];
        var key;
        for (key in O) {
          !has(hiddenKeys, key) && has(O, key) && result.push(key);
        }
        while (names.length > i) {
          if (has(O, key = names[i++])) {
            ~indexOf(result, key) || result.push(key);
          }
        }
        return result;
      };
    }, {
      '../internals/array-includes': 44,
      '../internals/has': 69,
      '../internals/hidden-keys': 70,
      '../internals/to-indexed-object': 113
    } ],
    95: [ function(_dereq_, module, exports) {
      var internalObjectKeys = _dereq_('../internals/object-keys-internal');
      var enumBugKeys = _dereq_('../internals/enum-bug-keys');
      module.exports = Object.keys || function keys(O) {
        return internalObjectKeys(O, enumBugKeys);
      };
    }, {
      '../internals/enum-bug-keys': 62,
      '../internals/object-keys-internal': 94
    } ],
    96: [ function(_dereq_, module, exports) {
      'use strict';
      var nativePropertyIsEnumerable = {}.propertyIsEnumerable;
      var getOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
      var NASHORN_BUG = getOwnPropertyDescriptor && !nativePropertyIsEnumerable.call({
        1: 2
      }, 1);
      exports.f = NASHORN_BUG ? function propertyIsEnumerable(V) {
        var descriptor = getOwnPropertyDescriptor(this, V);
        return !!descriptor && descriptor.enumerable;
      } : nativePropertyIsEnumerable;
    }, {} ],
    97: [ function(_dereq_, module, exports) {
      var anObject = _dereq_('../internals/an-object');
      var aPossiblePrototype = _dereq_('../internals/a-possible-prototype');
      module.exports = Object.setPrototypeOf || ('__proto__' in {} ? function() {
        var CORRECT_SETTER = false;
        var test = {};
        var setter;
        try {
          setter = Object.getOwnPropertyDescriptor(Object.prototype, '__proto__').set;
          setter.call(test, []);
          CORRECT_SETTER = test instanceof Array;
        } catch (error) {}
        return function setPrototypeOf(O, proto) {
          anObject(O);
          aPossiblePrototype(proto);
          if (CORRECT_SETTER) {
            setter.call(O, proto);
          } else {
            O.__proto__ = proto;
          }
          return O;
        };
      }() : undefined);
    }, {
      '../internals/a-possible-prototype': 35,
      '../internals/an-object': 38
    } ],
    98: [ function(_dereq_, module, exports) {
      'use strict';
      var TO_STRING_TAG_SUPPORT = _dereq_('../internals/to-string-tag-support');
      var classof = _dereq_('../internals/classof');
      module.exports = TO_STRING_TAG_SUPPORT ? {}.toString : function toString() {
        return '[object ' + classof(this) + ']';
      };
    }, {
      '../internals/classof': 53,
      '../internals/to-string-tag-support': 120
    } ],
    99: [ function(_dereq_, module, exports) {
      var getBuiltIn = _dereq_('../internals/get-built-in');
      var getOwnPropertyNamesModule = _dereq_('../internals/object-get-own-property-names');
      var getOwnPropertySymbolsModule = _dereq_('../internals/object-get-own-property-symbols');
      var anObject = _dereq_('../internals/an-object');
      module.exports = getBuiltIn('Reflect', 'ownKeys') || function ownKeys(it) {
        var keys = getOwnPropertyNamesModule.f(anObject(it));
        var getOwnPropertySymbols = getOwnPropertySymbolsModule.f;
        return getOwnPropertySymbols ? keys.concat(getOwnPropertySymbols(it)) : keys;
      };
    }, {
      '../internals/an-object': 38,
      '../internals/get-built-in': 66,
      '../internals/object-get-own-property-names': 91,
      '../internals/object-get-own-property-symbols': 92
    } ],
    100: [ function(_dereq_, module, exports) {
      var global = _dereq_('../internals/global');
      module.exports = global;
    }, {
      '../internals/global': 68
    } ],
    101: [ function(_dereq_, module, exports) {
      var redefine = _dereq_('../internals/redefine');
      module.exports = function(target, src, options) {
        for (var key in src) {
          redefine(target, key, src[key], options);
        }
        return target;
      };
    }, {
      '../internals/redefine': 102
    } ],
    102: [ function(_dereq_, module, exports) {
      var global = _dereq_('../internals/global');
      var createNonEnumerableProperty = _dereq_('../internals/create-non-enumerable-property');
      var has = _dereq_('../internals/has');
      var setGlobal = _dereq_('../internals/set-global');
      var inspectSource = _dereq_('../internals/inspect-source');
      var InternalStateModule = _dereq_('../internals/internal-state');
      var getInternalState = InternalStateModule.get;
      var enforceInternalState = InternalStateModule.enforce;
      var TEMPLATE = String(String).split('String');
      (module.exports = function(O, key, value, options) {
        var unsafe = options ? !!options.unsafe : false;
        var simple = options ? !!options.enumerable : false;
        var noTargetGet = options ? !!options.noTargetGet : false;
        if (typeof value == 'function') {
          if (typeof key == 'string' && !has(value, 'name')) {
            createNonEnumerableProperty(value, 'name', key);
          }
          enforceInternalState(value).source = TEMPLATE.join(typeof key == 'string' ? key : '');
        }
        if (O === global) {
          if (simple) {
            O[key] = value;
          } else {
            setGlobal(key, value);
          }
          return;
        } else if (!unsafe) {
          delete O[key];
        } else if (!noTargetGet && O[key]) {
          simple = true;
        }
        if (simple) {
          O[key] = value;
        } else {
          createNonEnumerableProperty(O, key, value);
        }
      })(Function.prototype, 'toString', function toString() {
        return typeof this == 'function' && getInternalState(this).source || inspectSource(this);
      });
    }, {
      '../internals/create-non-enumerable-property': 57,
      '../internals/global': 68,
      '../internals/has': 69,
      '../internals/inspect-source': 76,
      '../internals/internal-state': 77,
      '../internals/set-global': 104
    } ],
    103: [ function(_dereq_, module, exports) {
      module.exports = function(it) {
        if (it == undefined) {
          throw TypeError('Can\'t call method on ' + it);
        }
        return it;
      };
    }, {} ],
    104: [ function(_dereq_, module, exports) {
      var global = _dereq_('../internals/global');
      var createNonEnumerableProperty = _dereq_('../internals/create-non-enumerable-property');
      module.exports = function(key, value) {
        try {
          createNonEnumerableProperty(global, key, value);
        } catch (error) {
          global[key] = value;
        }
        return value;
      };
    }, {
      '../internals/create-non-enumerable-property': 57,
      '../internals/global': 68
    } ],
    105: [ function(_dereq_, module, exports) {
      'use strict';
      var getBuiltIn = _dereq_('../internals/get-built-in');
      var definePropertyModule = _dereq_('../internals/object-define-property');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var SPECIES = wellKnownSymbol('species');
      module.exports = function(CONSTRUCTOR_NAME) {
        var Constructor = getBuiltIn(CONSTRUCTOR_NAME);
        var defineProperty = definePropertyModule.f;
        if (DESCRIPTORS && Constructor && !Constructor[SPECIES]) {
          defineProperty(Constructor, SPECIES, {
            configurable: true,
            get: function() {
              return this;
            }
          });
        }
      };
    }, {
      '../internals/descriptors': 60,
      '../internals/get-built-in': 66,
      '../internals/object-define-property': 89,
      '../internals/well-known-symbol': 126
    } ],
    106: [ function(_dereq_, module, exports) {
      var defineProperty = _dereq_('../internals/object-define-property').f;
      var has = _dereq_('../internals/has');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var TO_STRING_TAG = wellKnownSymbol('toStringTag');
      module.exports = function(it, TAG, STATIC) {
        if (it && !has(it = STATIC ? it : it.prototype, TO_STRING_TAG)) {
          defineProperty(it, TO_STRING_TAG, {
            configurable: true,
            value: TAG
          });
        }
      };
    }, {
      '../internals/has': 69,
      '../internals/object-define-property': 89,
      '../internals/well-known-symbol': 126
    } ],
    107: [ function(_dereq_, module, exports) {
      var shared = _dereq_('../internals/shared');
      var uid = _dereq_('../internals/uid');
      var keys = shared('keys');
      module.exports = function(key) {
        return keys[key] || (keys[key] = uid(key));
      };
    }, {
      '../internals/shared': 109,
      '../internals/uid': 124
    } ],
    108: [ function(_dereq_, module, exports) {
      var global = _dereq_('../internals/global');
      var setGlobal = _dereq_('../internals/set-global');
      var SHARED = '__core-js_shared__';
      var store = global[SHARED] || setGlobal(SHARED, {});
      module.exports = store;
    }, {
      '../internals/global': 68,
      '../internals/set-global': 104
    } ],
    109: [ function(_dereq_, module, exports) {
      var IS_PURE = _dereq_('../internals/is-pure');
      var store = _dereq_('../internals/shared-store');
      (module.exports = function(key, value) {
        return store[key] || (store[key] = value !== undefined ? value : {});
      })('versions', []).push({
        version: '3.6.4',
        mode: IS_PURE ? 'pure' : 'global',
        copyright: '\xa9 2020 Denis Pushkarev (zloirock.ru)'
      });
    }, {
      '../internals/is-pure': 82,
      '../internals/shared-store': 108
    } ],
    110: [ function(_dereq_, module, exports) {
      var anObject = _dereq_('../internals/an-object');
      var aFunction = _dereq_('../internals/a-function');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var SPECIES = wellKnownSymbol('species');
      module.exports = function(O, defaultConstructor) {
        var C = anObject(O).constructor;
        var S;
        return C === undefined || (S = anObject(C)[SPECIES]) == undefined ? defaultConstructor : aFunction(S);
      };
    }, {
      '../internals/a-function': 34,
      '../internals/an-object': 38,
      '../internals/well-known-symbol': 126
    } ],
    111: [ function(_dereq_, module, exports) {
      var toInteger = _dereq_('../internals/to-integer');
      var max = Math.max;
      var min = Math.min;
      module.exports = function(index, length) {
        var integer = toInteger(index);
        return integer < 0 ? max(integer + length, 0) : min(integer, length);
      };
    }, {
      '../internals/to-integer': 114
    } ],
    112: [ function(_dereq_, module, exports) {
      var toInteger = _dereq_('../internals/to-integer');
      var toLength = _dereq_('../internals/to-length');
      module.exports = function(it) {
        if (it === undefined) {
          return 0;
        }
        var number = toInteger(it);
        var length = toLength(number);
        if (number !== length) {
          throw RangeError('Wrong length or index');
        }
        return length;
      };
    }, {
      '../internals/to-integer': 114,
      '../internals/to-length': 115
    } ],
    113: [ function(_dereq_, module, exports) {
      var IndexedObject = _dereq_('../internals/indexed-object');
      var requireObjectCoercible = _dereq_('../internals/require-object-coercible');
      module.exports = function(it) {
        return IndexedObject(requireObjectCoercible(it));
      };
    }, {
      '../internals/indexed-object': 74,
      '../internals/require-object-coercible': 103
    } ],
    114: [ function(_dereq_, module, exports) {
      var ceil = Math.ceil;
      var floor = Math.floor;
      module.exports = function(argument) {
        return isNaN(argument = +argument) ? 0 : (argument > 0 ? floor : ceil)(argument);
      };
    }, {} ],
    115: [ function(_dereq_, module, exports) {
      var toInteger = _dereq_('../internals/to-integer');
      var min = Math.min;
      module.exports = function(argument) {
        return argument > 0 ? min(toInteger(argument), 9007199254740991) : 0;
      };
    }, {
      '../internals/to-integer': 114
    } ],
    116: [ function(_dereq_, module, exports) {
      var requireObjectCoercible = _dereq_('../internals/require-object-coercible');
      module.exports = function(argument) {
        return Object(requireObjectCoercible(argument));
      };
    }, {
      '../internals/require-object-coercible': 103
    } ],
    117: [ function(_dereq_, module, exports) {
      var toPositiveInteger = _dereq_('../internals/to-positive-integer');
      module.exports = function(it, BYTES) {
        var offset = toPositiveInteger(it);
        if (offset % BYTES) {
          throw RangeError('Wrong offset');
        }
        return offset;
      };
    }, {
      '../internals/to-positive-integer': 118
    } ],
    118: [ function(_dereq_, module, exports) {
      var toInteger = _dereq_('../internals/to-integer');
      module.exports = function(it) {
        var result = toInteger(it);
        if (result < 0) {
          throw RangeError('The argument can\'t be less than 0');
        }
        return result;
      };
    }, {
      '../internals/to-integer': 114
    } ],
    119: [ function(_dereq_, module, exports) {
      var isObject = _dereq_('../internals/is-object');
      module.exports = function(input, PREFERRED_STRING) {
        if (!isObject(input)) {
          return input;
        }
        var fn, val;
        if (PREFERRED_STRING && typeof (fn = input.toString) == 'function' && !isObject(val = fn.call(input))) {
          return val;
        }
        if (typeof (fn = input.valueOf) == 'function' && !isObject(val = fn.call(input))) {
          return val;
        }
        if (!PREFERRED_STRING && typeof (fn = input.toString) == 'function' && !isObject(val = fn.call(input))) {
          return val;
        }
        throw TypeError('Can\'t convert object to primitive value');
      };
    }, {
      '../internals/is-object': 81
    } ],
    120: [ function(_dereq_, module, exports) {
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var TO_STRING_TAG = wellKnownSymbol('toStringTag');
      var test = {};
      test[TO_STRING_TAG] = 'z';
      module.exports = String(test) === '[object z]';
    }, {
      '../internals/well-known-symbol': 126
    } ],
    121: [ function(_dereq_, module, exports) {
      'use strict';
      var $ = _dereq_('../internals/export');
      var global = _dereq_('../internals/global');
      var DESCRIPTORS = _dereq_('../internals/descriptors');
      var TYPED_ARRAYS_CONSTRUCTORS_REQUIRES_WRAPPERS = _dereq_('../internals/typed-array-constructors-require-wrappers');
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var ArrayBufferModule = _dereq_('../internals/array-buffer');
      var anInstance = _dereq_('../internals/an-instance');
      var createPropertyDescriptor = _dereq_('../internals/create-property-descriptor');
      var createNonEnumerableProperty = _dereq_('../internals/create-non-enumerable-property');
      var toLength = _dereq_('../internals/to-length');
      var toIndex = _dereq_('../internals/to-index');
      var toOffset = _dereq_('../internals/to-offset');
      var toPrimitive = _dereq_('../internals/to-primitive');
      var has = _dereq_('../internals/has');
      var classof = _dereq_('../internals/classof');
      var isObject = _dereq_('../internals/is-object');
      var create = _dereq_('../internals/object-create');
      var setPrototypeOf = _dereq_('../internals/object-set-prototype-of');
      var getOwnPropertyNames = _dereq_('../internals/object-get-own-property-names').f;
      var typedArrayFrom = _dereq_('../internals/typed-array-from');
      var forEach = _dereq_('../internals/array-iteration').forEach;
      var setSpecies = _dereq_('../internals/set-species');
      var definePropertyModule = _dereq_('../internals/object-define-property');
      var getOwnPropertyDescriptorModule = _dereq_('../internals/object-get-own-property-descriptor');
      var InternalStateModule = _dereq_('../internals/internal-state');
      var inheritIfRequired = _dereq_('../internals/inherit-if-required');
      var getInternalState = InternalStateModule.get;
      var setInternalState = InternalStateModule.set;
      var nativeDefineProperty = definePropertyModule.f;
      var nativeGetOwnPropertyDescriptor = getOwnPropertyDescriptorModule.f;
      var round = Math.round;
      var RangeError = global.RangeError;
      var ArrayBuffer = ArrayBufferModule.ArrayBuffer;
      var DataView = ArrayBufferModule.DataView;
      var NATIVE_ARRAY_BUFFER_VIEWS = ArrayBufferViewCore.NATIVE_ARRAY_BUFFER_VIEWS;
      var TYPED_ARRAY_TAG = ArrayBufferViewCore.TYPED_ARRAY_TAG;
      var TypedArray = ArrayBufferViewCore.TypedArray;
      var TypedArrayPrototype = ArrayBufferViewCore.TypedArrayPrototype;
      var aTypedArrayConstructor = ArrayBufferViewCore.aTypedArrayConstructor;
      var isTypedArray = ArrayBufferViewCore.isTypedArray;
      var BYTES_PER_ELEMENT = 'BYTES_PER_ELEMENT';
      var WRONG_LENGTH = 'Wrong length';
      var fromList = function(C, list) {
        var index = 0;
        var length = list.length;
        var result = new (aTypedArrayConstructor(C))(length);
        while (length > index) {
          result[index] = list[index++];
        }
        return result;
      };
      var addGetter = function(it, key) {
        nativeDefineProperty(it, key, {
          get: function() {
            return getInternalState(this)[key];
          }
        });
      };
      var isArrayBuffer = function(it) {
        var klass;
        return it instanceof ArrayBuffer || (klass = classof(it)) == 'ArrayBuffer' || klass == 'SharedArrayBuffer';
      };
      var isTypedArrayIndex = function(target, key) {
        return isTypedArray(target) && typeof key != 'symbol' && key in target && String(+key) == String(key);
      };
      var wrappedGetOwnPropertyDescriptor = function getOwnPropertyDescriptor(target, key) {
        return isTypedArrayIndex(target, key = toPrimitive(key, true)) ? createPropertyDescriptor(2, target[key]) : nativeGetOwnPropertyDescriptor(target, key);
      };
      var wrappedDefineProperty = function defineProperty(target, key, descriptor) {
        if (isTypedArrayIndex(target, key = toPrimitive(key, true)) && isObject(descriptor) && has(descriptor, 'value') && !has(descriptor, 'get') && !has(descriptor, 'set') && !descriptor.configurable && (!has(descriptor, 'writable') || descriptor.writable) && (!has(descriptor, 'enumerable') || descriptor.enumerable)) {
          target[key] = descriptor.value;
          return target;
        }
        return nativeDefineProperty(target, key, descriptor);
      };
      if (DESCRIPTORS) {
        if (!NATIVE_ARRAY_BUFFER_VIEWS) {
          getOwnPropertyDescriptorModule.f = wrappedGetOwnPropertyDescriptor;
          definePropertyModule.f = wrappedDefineProperty;
          addGetter(TypedArrayPrototype, 'buffer');
          addGetter(TypedArrayPrototype, 'byteOffset');
          addGetter(TypedArrayPrototype, 'byteLength');
          addGetter(TypedArrayPrototype, 'length');
        }
        $({
          target: 'Object',
          stat: true,
          forced: !NATIVE_ARRAY_BUFFER_VIEWS
        }, {
          getOwnPropertyDescriptor: wrappedGetOwnPropertyDescriptor,
          defineProperty: wrappedDefineProperty
        });
        module.exports = function(TYPE, wrapper, CLAMPED) {
          var BYTES = TYPE.match(/\d+$/)[0] / 8;
          var CONSTRUCTOR_NAME = TYPE + (CLAMPED ? 'Clamped' : '') + 'Array';
          var GETTER = 'get' + TYPE;
          var SETTER = 'set' + TYPE;
          var NativeTypedArrayConstructor = global[CONSTRUCTOR_NAME];
          var TypedArrayConstructor = NativeTypedArrayConstructor;
          var TypedArrayConstructorPrototype = TypedArrayConstructor && TypedArrayConstructor.prototype;
          var exported = {};
          var getter = function(that, index) {
            var data = getInternalState(that);
            return data.view[GETTER](index * BYTES + data.byteOffset, true);
          };
          var setter = function(that, index, value) {
            var data = getInternalState(that);
            if (CLAMPED) {
              value = (value = round(value)) < 0 ? 0 : value > 255 ? 255 : value & 255;
            }
            data.view[SETTER](index * BYTES + data.byteOffset, value, true);
          };
          var addElement = function(that, index) {
            nativeDefineProperty(that, index, {
              get: function() {
                return getter(this, index);
              },
              set: function(value) {
                return setter(this, index, value);
              },
              enumerable: true
            });
          };
          if (!NATIVE_ARRAY_BUFFER_VIEWS) {
            TypedArrayConstructor = wrapper(function(that, data, offset, $length) {
              anInstance(that, TypedArrayConstructor, CONSTRUCTOR_NAME);
              var index = 0;
              var byteOffset = 0;
              var buffer, byteLength, length;
              if (!isObject(data)) {
                length = toIndex(data);
                byteLength = length * BYTES;
                buffer = new ArrayBuffer(byteLength);
              } else if (isArrayBuffer(data)) {
                buffer = data;
                byteOffset = toOffset(offset, BYTES);
                var $len = data.byteLength;
                if ($length === undefined) {
                  if ($len % BYTES) {
                    throw RangeError(WRONG_LENGTH);
                  }
                  byteLength = $len - byteOffset;
                  if (byteLength < 0) {
                    throw RangeError(WRONG_LENGTH);
                  }
                } else {
                  byteLength = toLength($length) * BYTES;
                  if (byteLength + byteOffset > $len) {
                    throw RangeError(WRONG_LENGTH);
                  }
                }
                length = byteLength / BYTES;
              } else if (isTypedArray(data)) {
                return fromList(TypedArrayConstructor, data);
              } else {
                return typedArrayFrom.call(TypedArrayConstructor, data);
              }
              setInternalState(that, {
                buffer: buffer,
                byteOffset: byteOffset,
                byteLength: byteLength,
                length: length,
                view: new DataView(buffer)
              });
              while (index < length) {
                addElement(that, index++);
              }
            });
            if (setPrototypeOf) {
              setPrototypeOf(TypedArrayConstructor, TypedArray);
            }
            TypedArrayConstructorPrototype = TypedArrayConstructor.prototype = create(TypedArrayPrototype);
          } else if (TYPED_ARRAYS_CONSTRUCTORS_REQUIRES_WRAPPERS) {
            TypedArrayConstructor = wrapper(function(dummy, data, typedArrayOffset, $length) {
              anInstance(dummy, TypedArrayConstructor, CONSTRUCTOR_NAME);
              return inheritIfRequired(function() {
                if (!isObject(data)) {
                  return new NativeTypedArrayConstructor(toIndex(data));
                }
                if (isArrayBuffer(data)) {
                  return $length !== undefined ? new NativeTypedArrayConstructor(data, toOffset(typedArrayOffset, BYTES), $length) : typedArrayOffset !== undefined ? new NativeTypedArrayConstructor(data, toOffset(typedArrayOffset, BYTES)) : new NativeTypedArrayConstructor(data);
                }
                if (isTypedArray(data)) {
                  return fromList(TypedArrayConstructor, data);
                }
                return typedArrayFrom.call(TypedArrayConstructor, data);
              }(), dummy, TypedArrayConstructor);
            });
            if (setPrototypeOf) {
              setPrototypeOf(TypedArrayConstructor, TypedArray);
            }
            forEach(getOwnPropertyNames(NativeTypedArrayConstructor), function(key) {
              if (!(key in TypedArrayConstructor)) {
                createNonEnumerableProperty(TypedArrayConstructor, key, NativeTypedArrayConstructor[key]);
              }
            });
            TypedArrayConstructor.prototype = TypedArrayConstructorPrototype;
          }
          if (TypedArrayConstructorPrototype.constructor !== TypedArrayConstructor) {
            createNonEnumerableProperty(TypedArrayConstructorPrototype, 'constructor', TypedArrayConstructor);
          }
          if (TYPED_ARRAY_TAG) {
            createNonEnumerableProperty(TypedArrayConstructorPrototype, TYPED_ARRAY_TAG, CONSTRUCTOR_NAME);
          }
          exported[CONSTRUCTOR_NAME] = TypedArrayConstructor;
          $({
            global: true,
            forced: TypedArrayConstructor != NativeTypedArrayConstructor,
            sham: !NATIVE_ARRAY_BUFFER_VIEWS
          }, exported);
          if (!(BYTES_PER_ELEMENT in TypedArrayConstructor)) {
            createNonEnumerableProperty(TypedArrayConstructor, BYTES_PER_ELEMENT, BYTES);
          }
          if (!(BYTES_PER_ELEMENT in TypedArrayConstructorPrototype)) {
            createNonEnumerableProperty(TypedArrayConstructorPrototype, BYTES_PER_ELEMENT, BYTES);
          }
          setSpecies(CONSTRUCTOR_NAME);
        };
      } else {
        module.exports = function() {};
      }
    }, {
      '../internals/an-instance': 37,
      '../internals/array-buffer': 41,
      '../internals/array-buffer-view-core': 40,
      '../internals/array-iteration': 45,
      '../internals/classof': 53,
      '../internals/create-non-enumerable-property': 57,
      '../internals/create-property-descriptor': 58,
      '../internals/descriptors': 60,
      '../internals/export': 63,
      '../internals/global': 68,
      '../internals/has': 69,
      '../internals/inherit-if-required': 75,
      '../internals/internal-state': 77,
      '../internals/is-object': 81,
      '../internals/object-create': 87,
      '../internals/object-define-property': 89,
      '../internals/object-get-own-property-descriptor': 90,
      '../internals/object-get-own-property-names': 91,
      '../internals/object-set-prototype-of': 97,
      '../internals/set-species': 105,
      '../internals/to-index': 112,
      '../internals/to-length': 115,
      '../internals/to-offset': 117,
      '../internals/to-primitive': 119,
      '../internals/typed-array-constructors-require-wrappers': 122,
      '../internals/typed-array-from': 123
    } ],
    122: [ function(_dereq_, module, exports) {
      var global = _dereq_('../internals/global');
      var fails = _dereq_('../internals/fails');
      var checkCorrectnessOfIteration = _dereq_('../internals/check-correctness-of-iteration');
      var NATIVE_ARRAY_BUFFER_VIEWS = _dereq_('../internals/array-buffer-view-core').NATIVE_ARRAY_BUFFER_VIEWS;
      var ArrayBuffer = global.ArrayBuffer;
      var Int8Array = global.Int8Array;
      module.exports = !NATIVE_ARRAY_BUFFER_VIEWS || !fails(function() {
        Int8Array(1);
      }) || !fails(function() {
        new Int8Array(-1);
      }) || !checkCorrectnessOfIteration(function(iterable) {
        new Int8Array();
        new Int8Array(null);
        new Int8Array(1.5);
        new Int8Array(iterable);
      }, true) || fails(function() {
        return new Int8Array(new ArrayBuffer(2), 1, undefined).length !== 1;
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/check-correctness-of-iteration': 51,
      '../internals/fails': 64,
      '../internals/global': 68
    } ],
    123: [ function(_dereq_, module, exports) {
      var toObject = _dereq_('../internals/to-object');
      var toLength = _dereq_('../internals/to-length');
      var getIteratorMethod = _dereq_('../internals/get-iterator-method');
      var isArrayIteratorMethod = _dereq_('../internals/is-array-iterator-method');
      var bind = _dereq_('../internals/function-bind-context');
      var aTypedArrayConstructor = _dereq_('../internals/array-buffer-view-core').aTypedArrayConstructor;
      module.exports = function from(source) {
        var O = toObject(source);
        var argumentsLength = arguments.length;
        var mapfn = argumentsLength > 1 ? arguments[1] : undefined;
        var mapping = mapfn !== undefined;
        var iteratorMethod = getIteratorMethod(O);
        var i, length, result, step, iterator, next;
        if (iteratorMethod != undefined && !isArrayIteratorMethod(iteratorMethod)) {
          iterator = iteratorMethod.call(O);
          next = iterator.next;
          O = [];
          while (!(step = next.call(iterator)).done) {
            O.push(step.value);
          }
        }
        if (mapping && argumentsLength > 2) {
          mapfn = bind(mapfn, arguments[2], 2);
        }
        length = toLength(O.length);
        result = new (aTypedArrayConstructor(this))(length);
        for (i = 0; length > i; i++) {
          result[i] = mapping ? mapfn(O[i], i) : O[i];
        }
        return result;
      };
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/function-bind-context': 65,
      '../internals/get-iterator-method': 67,
      '../internals/is-array-iterator-method': 78,
      '../internals/to-length': 115,
      '../internals/to-object': 116
    } ],
    124: [ function(_dereq_, module, exports) {
      var id = 0;
      var postfix = Math.random();
      module.exports = function(key) {
        return 'Symbol(' + String(key === undefined ? '' : key) + ')_' + (++id + postfix).toString(36);
      };
    }, {} ],
    125: [ function(_dereq_, module, exports) {
      var NATIVE_SYMBOL = _dereq_('../internals/native-symbol');
      module.exports = NATIVE_SYMBOL && !Symbol.sham && typeof Symbol.iterator == 'symbol';
    }, {
      '../internals/native-symbol': 85
    } ],
    126: [ function(_dereq_, module, exports) {
      var global = _dereq_('../internals/global');
      var shared = _dereq_('../internals/shared');
      var has = _dereq_('../internals/has');
      var uid = _dereq_('../internals/uid');
      var NATIVE_SYMBOL = _dereq_('../internals/native-symbol');
      var USE_SYMBOL_AS_UID = _dereq_('../internals/use-symbol-as-uid');
      var WellKnownSymbolsStore = shared('wks');
      var Symbol = global.Symbol;
      var createWellKnownSymbol = USE_SYMBOL_AS_UID ? Symbol : Symbol && Symbol.withoutSetter || uid;
      module.exports = function(name) {
        if (!has(WellKnownSymbolsStore, name)) {
          if (NATIVE_SYMBOL && has(Symbol, name)) {
            WellKnownSymbolsStore[name] = Symbol[name];
          } else {
            WellKnownSymbolsStore[name] = createWellKnownSymbol('Symbol.' + name);
          }
        }
        return WellKnownSymbolsStore[name];
      };
    }, {
      '../internals/global': 68,
      '../internals/has': 69,
      '../internals/native-symbol': 85,
      '../internals/shared': 109,
      '../internals/uid': 124,
      '../internals/use-symbol-as-uid': 125
    } ],
    127: [ function(_dereq_, module, exports) {
      'use strict';
      var toIndexedObject = _dereq_('../internals/to-indexed-object');
      var addToUnscopables = _dereq_('../internals/add-to-unscopables');
      var Iterators = _dereq_('../internals/iterators');
      var InternalStateModule = _dereq_('../internals/internal-state');
      var defineIterator = _dereq_('../internals/define-iterator');
      var ARRAY_ITERATOR = 'Array Iterator';
      var setInternalState = InternalStateModule.set;
      var getInternalState = InternalStateModule.getterFor(ARRAY_ITERATOR);
      module.exports = defineIterator(Array, 'Array', function(iterated, kind) {
        setInternalState(this, {
          type: ARRAY_ITERATOR,
          target: toIndexedObject(iterated),
          index: 0,
          kind: kind
        });
      }, function() {
        var state = getInternalState(this);
        var target = state.target;
        var kind = state.kind;
        var index = state.index++;
        if (!target || index >= target.length) {
          state.target = undefined;
          return {
            value: undefined,
            done: true
          };
        }
        if (kind == 'keys') {
          return {
            value: index,
            done: false
          };
        }
        if (kind == 'values') {
          return {
            value: target[index],
            done: false
          };
        }
        return {
          value: [ index, target[index] ],
          done: false
        };
      }, 'values');
      Iterators.Arguments = Iterators.Array;
      addToUnscopables('keys');
      addToUnscopables('values');
      addToUnscopables('entries');
    }, {
      '../internals/add-to-unscopables': 36,
      '../internals/define-iterator': 59,
      '../internals/internal-state': 77,
      '../internals/iterators': 84,
      '../internals/to-indexed-object': 113
    } ],
    128: [ function(_dereq_, module, exports) {
      var TO_STRING_TAG_SUPPORT = _dereq_('../internals/to-string-tag-support');
      var redefine = _dereq_('../internals/redefine');
      var toString = _dereq_('../internals/object-to-string');
      if (!TO_STRING_TAG_SUPPORT) {
        redefine(Object.prototype, 'toString', toString, {
          unsafe: true
        });
      }
    }, {
      '../internals/object-to-string': 98,
      '../internals/redefine': 102,
      '../internals/to-string-tag-support': 120
    } ],
    129: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $copyWithin = _dereq_('../internals/array-copy-within');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('copyWithin', function copyWithin(target, start) {
        return $copyWithin.call(aTypedArray(this), target, start, arguments.length > 2 ? arguments[2] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-copy-within': 42
    } ],
    130: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $every = _dereq_('../internals/array-iteration').every;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('every', function every(callbackfn) {
        return $every(aTypedArray(this), callbackfn, arguments.length > 1 ? arguments[1] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-iteration': 45
    } ],
    131: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $fill = _dereq_('../internals/array-fill');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('fill', function fill(value) {
        return $fill.apply(aTypedArray(this), arguments);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-fill': 43
    } ],
    132: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $filter = _dereq_('../internals/array-iteration').filter;
      var speciesConstructor = _dereq_('../internals/species-constructor');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var aTypedArrayConstructor = ArrayBufferViewCore.aTypedArrayConstructor;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('filter', function filter(callbackfn) {
        var list = $filter(aTypedArray(this), callbackfn, arguments.length > 1 ? arguments[1] : undefined);
        var C = speciesConstructor(this, this.constructor);
        var index = 0;
        var length = list.length;
        var result = new (aTypedArrayConstructor(C))(length);
        while (length > index) {
          result[index] = list[index++];
        }
        return result;
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-iteration': 45,
      '../internals/species-constructor': 110
    } ],
    133: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $findIndex = _dereq_('../internals/array-iteration').findIndex;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('findIndex', function findIndex(predicate) {
        return $findIndex(aTypedArray(this), predicate, arguments.length > 1 ? arguments[1] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-iteration': 45
    } ],
    134: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $find = _dereq_('../internals/array-iteration').find;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('find', function find(predicate) {
        return $find(aTypedArray(this), predicate, arguments.length > 1 ? arguments[1] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-iteration': 45
    } ],
    135: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $forEach = _dereq_('../internals/array-iteration').forEach;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('forEach', function forEach(callbackfn) {
        $forEach(aTypedArray(this), callbackfn, arguments.length > 1 ? arguments[1] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-iteration': 45
    } ],
    136: [ function(_dereq_, module, exports) {
      'use strict';
      var TYPED_ARRAYS_CONSTRUCTORS_REQUIRES_WRAPPERS = _dereq_('../internals/typed-array-constructors-require-wrappers');
      var exportTypedArrayStaticMethod = _dereq_('../internals/array-buffer-view-core').exportTypedArrayStaticMethod;
      var typedArrayFrom = _dereq_('../internals/typed-array-from');
      exportTypedArrayStaticMethod('from', typedArrayFrom, TYPED_ARRAYS_CONSTRUCTORS_REQUIRES_WRAPPERS);
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/typed-array-constructors-require-wrappers': 122,
      '../internals/typed-array-from': 123
    } ],
    137: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $includes = _dereq_('../internals/array-includes').includes;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('includes', function includes(searchElement) {
        return $includes(aTypedArray(this), searchElement, arguments.length > 1 ? arguments[1] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-includes': 44
    } ],
    138: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $indexOf = _dereq_('../internals/array-includes').indexOf;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('indexOf', function indexOf(searchElement) {
        return $indexOf(aTypedArray(this), searchElement, arguments.length > 1 ? arguments[1] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-includes': 44
    } ],
    139: [ function(_dereq_, module, exports) {
      'use strict';
      var global = _dereq_('../internals/global');
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var ArrayIterators = _dereq_('../modules/es.array.iterator');
      var wellKnownSymbol = _dereq_('../internals/well-known-symbol');
      var ITERATOR = wellKnownSymbol('iterator');
      var Uint8Array = global.Uint8Array;
      var arrayValues = ArrayIterators.values;
      var arrayKeys = ArrayIterators.keys;
      var arrayEntries = ArrayIterators.entries;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      var nativeTypedArrayIterator = Uint8Array && Uint8Array.prototype[ITERATOR];
      var CORRECT_ITER_NAME = !!nativeTypedArrayIterator && (nativeTypedArrayIterator.name == 'values' || nativeTypedArrayIterator.name == undefined);
      var typedArrayValues = function values() {
        return arrayValues.call(aTypedArray(this));
      };
      exportTypedArrayMethod('entries', function entries() {
        return arrayEntries.call(aTypedArray(this));
      });
      exportTypedArrayMethod('keys', function keys() {
        return arrayKeys.call(aTypedArray(this));
      });
      exportTypedArrayMethod('values', typedArrayValues, !CORRECT_ITER_NAME);
      exportTypedArrayMethod(ITERATOR, typedArrayValues, !CORRECT_ITER_NAME);
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/global': 68,
      '../internals/well-known-symbol': 126,
      '../modules/es.array.iterator': 127
    } ],
    140: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      var $join = [].join;
      exportTypedArrayMethod('join', function join(separator) {
        return $join.apply(aTypedArray(this), arguments);
      });
    }, {
      '../internals/array-buffer-view-core': 40
    } ],
    141: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $lastIndexOf = _dereq_('../internals/array-last-index-of');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('lastIndexOf', function lastIndexOf(searchElement) {
        return $lastIndexOf.apply(aTypedArray(this), arguments);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-last-index-of': 46
    } ],
    142: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $map = _dereq_('../internals/array-iteration').map;
      var speciesConstructor = _dereq_('../internals/species-constructor');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var aTypedArrayConstructor = ArrayBufferViewCore.aTypedArrayConstructor;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('map', function map(mapfn) {
        return $map(aTypedArray(this), mapfn, arguments.length > 1 ? arguments[1] : undefined, function(O, length) {
          return new (aTypedArrayConstructor(speciesConstructor(O, O.constructor)))(length);
        });
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-iteration': 45,
      '../internals/species-constructor': 110
    } ],
    143: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var TYPED_ARRAYS_CONSTRUCTORS_REQUIRES_WRAPPERS = _dereq_('../internals/typed-array-constructors-require-wrappers');
      var aTypedArrayConstructor = ArrayBufferViewCore.aTypedArrayConstructor;
      var exportTypedArrayStaticMethod = ArrayBufferViewCore.exportTypedArrayStaticMethod;
      exportTypedArrayStaticMethod('of', function of() {
        var index = 0;
        var length = arguments.length;
        var result = new (aTypedArrayConstructor(this))(length);
        while (length > index) {
          result[index] = arguments[index++];
        }
        return result;
      }, TYPED_ARRAYS_CONSTRUCTORS_REQUIRES_WRAPPERS);
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/typed-array-constructors-require-wrappers': 122
    } ],
    144: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $reduceRight = _dereq_('../internals/array-reduce').right;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('reduceRight', function reduceRight(callbackfn) {
        return $reduceRight(aTypedArray(this), callbackfn, arguments.length, arguments.length > 1 ? arguments[1] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-reduce': 49
    } ],
    145: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $reduce = _dereq_('../internals/array-reduce').left;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('reduce', function reduce(callbackfn) {
        return $reduce(aTypedArray(this), callbackfn, arguments.length, arguments.length > 1 ? arguments[1] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-reduce': 49
    } ],
    146: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      var floor = Math.floor;
      exportTypedArrayMethod('reverse', function reverse() {
        var that = this;
        var length = aTypedArray(that).length;
        var middle = floor(length / 2);
        var index = 0;
        var value;
        while (index < middle) {
          value = that[index];
          that[index++] = that[--length];
          that[length] = value;
        }
        return that;
      });
    }, {
      '../internals/array-buffer-view-core': 40
    } ],
    147: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var toLength = _dereq_('../internals/to-length');
      var toOffset = _dereq_('../internals/to-offset');
      var toObject = _dereq_('../internals/to-object');
      var fails = _dereq_('../internals/fails');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      var FORCED = fails(function() {
        new Int8Array(1).set({});
      });
      exportTypedArrayMethod('set', function set(arrayLike) {
        aTypedArray(this);
        var offset = toOffset(arguments.length > 1 ? arguments[1] : undefined, 1);
        var length = this.length;
        var src = toObject(arrayLike);
        var len = toLength(src.length);
        var index = 0;
        if (len + offset > length) {
          throw RangeError('Wrong length');
        }
        while (index < len) {
          this[offset + index] = src[index++];
        }
      }, FORCED);
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/fails': 64,
      '../internals/to-length': 115,
      '../internals/to-object': 116,
      '../internals/to-offset': 117
    } ],
    148: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var speciesConstructor = _dereq_('../internals/species-constructor');
      var fails = _dereq_('../internals/fails');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var aTypedArrayConstructor = ArrayBufferViewCore.aTypedArrayConstructor;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      var $slice = [].slice;
      var FORCED = fails(function() {
        new Int8Array(1).slice();
      });
      exportTypedArrayMethod('slice', function slice(start, end) {
        var list = $slice.call(aTypedArray(this), start, end);
        var C = speciesConstructor(this, this.constructor);
        var index = 0;
        var length = list.length;
        var result = new (aTypedArrayConstructor(C))(length);
        while (length > index) {
          result[index] = list[index++];
        }
        return result;
      }, FORCED);
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/fails': 64,
      '../internals/species-constructor': 110
    } ],
    149: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var $some = _dereq_('../internals/array-iteration').some;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('some', function some(callbackfn) {
        return $some(aTypedArray(this), callbackfn, arguments.length > 1 ? arguments[1] : undefined);
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/array-iteration': 45
    } ],
    150: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      var $sort = [].sort;
      exportTypedArrayMethod('sort', function sort(comparefn) {
        return $sort.call(aTypedArray(this), comparefn);
      });
    }, {
      '../internals/array-buffer-view-core': 40
    } ],
    151: [ function(_dereq_, module, exports) {
      'use strict';
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var toLength = _dereq_('../internals/to-length');
      var toAbsoluteIndex = _dereq_('../internals/to-absolute-index');
      var speciesConstructor = _dereq_('../internals/species-constructor');
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      exportTypedArrayMethod('subarray', function subarray(begin, end) {
        var O = aTypedArray(this);
        var length = O.length;
        var beginIndex = toAbsoluteIndex(begin, length);
        return new (speciesConstructor(O, O.constructor))(O.buffer, O.byteOffset + beginIndex * O.BYTES_PER_ELEMENT, toLength((end === undefined ? length : toAbsoluteIndex(end, length)) - beginIndex));
      });
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/species-constructor': 110,
      '../internals/to-absolute-index': 111,
      '../internals/to-length': 115
    } ],
    152: [ function(_dereq_, module, exports) {
      'use strict';
      var global = _dereq_('../internals/global');
      var ArrayBufferViewCore = _dereq_('../internals/array-buffer-view-core');
      var fails = _dereq_('../internals/fails');
      var Int8Array = global.Int8Array;
      var aTypedArray = ArrayBufferViewCore.aTypedArray;
      var exportTypedArrayMethod = ArrayBufferViewCore.exportTypedArrayMethod;
      var $toLocaleString = [].toLocaleString;
      var $slice = [].slice;
      var TO_LOCALE_STRING_BUG = !!Int8Array && fails(function() {
        $toLocaleString.call(new Int8Array(1));
      });
      var FORCED = fails(function() {
        return [ 1, 2 ].toLocaleString() != new Int8Array([ 1, 2 ]).toLocaleString();
      }) || !fails(function() {
        Int8Array.prototype.toLocaleString.call([ 1, 2 ]);
      });
      exportTypedArrayMethod('toLocaleString', function toLocaleString() {
        return $toLocaleString.apply(TO_LOCALE_STRING_BUG ? $slice.call(aTypedArray(this)) : aTypedArray(this), arguments);
      }, FORCED);
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/fails': 64,
      '../internals/global': 68
    } ],
    153: [ function(_dereq_, module, exports) {
      'use strict';
      var exportTypedArrayMethod = _dereq_('../internals/array-buffer-view-core').exportTypedArrayMethod;
      var fails = _dereq_('../internals/fails');
      var global = _dereq_('../internals/global');
      var Uint8Array = global.Uint8Array;
      var Uint8ArrayPrototype = Uint8Array && Uint8Array.prototype || {};
      var arrayToString = [].toString;
      var arrayJoin = [].join;
      if (fails(function() {
        arrayToString.call({});
      })) {
        arrayToString = function toString() {
          return arrayJoin.call(this);
        };
      }
      var IS_NOT_ARRAY_METHOD = Uint8ArrayPrototype.toString != arrayToString;
      exportTypedArrayMethod('toString', arrayToString, IS_NOT_ARRAY_METHOD);
    }, {
      '../internals/array-buffer-view-core': 40,
      '../internals/fails': 64,
      '../internals/global': 68
    } ],
    154: [ function(_dereq_, module, exports) {
      var createTypedArrayConstructor = _dereq_('../internals/typed-array-constructor');
      createTypedArrayConstructor('Uint32', function(init) {
        return function Uint32Array(data, byteOffset, length) {
          return init(this, data, byteOffset, length);
        };
      });
    }, {
      '../internals/typed-array-constructor': 121
    } ],
    155: [ function(_dereq_, module, exports) {
      module.exports = {
        CssSelectorParser: _dereq_('./lib/css-selector-parser.js').CssSelectorParser
      };
    }, {
      './lib/css-selector-parser.js': 156
    } ],
    156: [ function(_dereq_, module, exports) {
      function CssSelectorParser() {
        this.pseudos = {};
        this.attrEqualityMods = {};
        this.ruleNestingOperators = {};
        this.substitutesEnabled = false;
      }
      CssSelectorParser.prototype.registerSelectorPseudos = function(name) {
        for (var j = 0, len = arguments.length; j < len; j++) {
          name = arguments[j];
          this.pseudos[name] = 'selector';
        }
        return this;
      };
      CssSelectorParser.prototype.unregisterSelectorPseudos = function(name) {
        for (var j = 0, len = arguments.length; j < len; j++) {
          name = arguments[j];
          delete this.pseudos[name];
        }
        return this;
      };
      CssSelectorParser.prototype.registerNumericPseudos = function(name) {
        for (var j = 0, len = arguments.length; j < len; j++) {
          name = arguments[j];
          this.pseudos[name] = 'numeric';
        }
        return this;
      };
      CssSelectorParser.prototype.unregisterNumericPseudos = function(name) {
        for (var j = 0, len = arguments.length; j < len; j++) {
          name = arguments[j];
          delete this.pseudos[name];
        }
        return this;
      };
      CssSelectorParser.prototype.registerNestingOperators = function(operator) {
        for (var j = 0, len = arguments.length; j < len; j++) {
          operator = arguments[j];
          this.ruleNestingOperators[operator] = true;
        }
        return this;
      };
      CssSelectorParser.prototype.unregisterNestingOperators = function(operator) {
        for (var j = 0, len = arguments.length; j < len; j++) {
          operator = arguments[j];
          delete this.ruleNestingOperators[operator];
        }
        return this;
      };
      CssSelectorParser.prototype.registerAttrEqualityMods = function(mod) {
        for (var j = 0, len = arguments.length; j < len; j++) {
          mod = arguments[j];
          this.attrEqualityMods[mod] = true;
        }
        return this;
      };
      CssSelectorParser.prototype.unregisterAttrEqualityMods = function(mod) {
        for (var j = 0, len = arguments.length; j < len; j++) {
          mod = arguments[j];
          delete this.attrEqualityMods[mod];
        }
        return this;
      };
      CssSelectorParser.prototype.enableSubstitutes = function() {
        this.substitutesEnabled = true;
        return this;
      };
      CssSelectorParser.prototype.disableSubstitutes = function() {
        this.substitutesEnabled = false;
        return this;
      };
      function isIdentStart(c) {
        return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c === '-' || c === '_';
      }
      function isIdent(c) {
        return c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c === '-' || c === '_';
      }
      function isHex(c) {
        return c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F' || c >= '0' && c <= '9';
      }
      function isDecimal(c) {
        return c >= '0' && c <= '9';
      }
      function isAttrMatchOperator(chr) {
        return chr === '=' || chr === '^' || chr === '$' || chr === '*' || chr === '~';
      }
      var identSpecialChars = {
        '!': true,
        '"': true,
        '#': true,
        $: true,
        '%': true,
        '&': true,
        '\'': true,
        '(': true,
        ')': true,
        '*': true,
        '+': true,
        ',': true,
        '.': true,
        '/': true,
        ';': true,
        '<': true,
        '=': true,
        '>': true,
        '?': true,
        '@': true,
        '[': true,
        '\\': true,
        ']': true,
        '^': true,
        '`': true,
        '{': true,
        '|': true,
        '}': true,
        '~': true
      };
      var strReplacementsRev = {
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
        '\f': '\\f',
        '\v': '\\v'
      };
      var singleQuoteEscapeChars = {
        n: '\n',
        r: '\r',
        t: '\t',
        f: '\f',
        '\\': '\\',
        '\'': '\''
      };
      var doubleQuotesEscapeChars = {
        n: '\n',
        r: '\r',
        t: '\t',
        f: '\f',
        '\\': '\\',
        '"': '"'
      };
      function ParseContext(str, pos, pseudos, attrEqualityMods, ruleNestingOperators, substitutesEnabled) {
        var chr, getIdent, getStr, l, skipWhitespace;
        l = str.length;
        chr = null;
        getStr = function(quote, escapeTable) {
          var esc, hex, result;
          result = '';
          pos++;
          chr = str.charAt(pos);
          while (pos < l) {
            if (chr === quote) {
              pos++;
              return result;
            } else if (chr === '\\') {
              pos++;
              chr = str.charAt(pos);
              if (chr === quote) {
                result += quote;
              } else if (esc = escapeTable[chr]) {
                result += esc;
              } else if (isHex(chr)) {
                hex = chr;
                pos++;
                chr = str.charAt(pos);
                while (isHex(chr)) {
                  hex += chr;
                  pos++;
                  chr = str.charAt(pos);
                }
                if (chr === ' ') {
                  pos++;
                  chr = str.charAt(pos);
                }
                result += String.fromCharCode(parseInt(hex, 16));
                continue;
              } else {
                result += chr;
              }
            } else {
              result += chr;
            }
            pos++;
            chr = str.charAt(pos);
          }
          return result;
        };
        getIdent = function() {
          var result = '';
          chr = str.charAt(pos);
          while (pos < l) {
            if (isIdent(chr)) {
              result += chr;
            } else if (chr === '\\') {
              pos++;
              if (pos >= l) {
                throw Error('Expected symbol but end of file reached.');
              }
              chr = str.charAt(pos);
              if (identSpecialChars[chr]) {
                result += chr;
              } else if (isHex(chr)) {
                var hex = chr;
                pos++;
                chr = str.charAt(pos);
                while (isHex(chr)) {
                  hex += chr;
                  pos++;
                  chr = str.charAt(pos);
                }
                if (chr === ' ') {
                  pos++;
                  chr = str.charAt(pos);
                }
                result += String.fromCharCode(parseInt(hex, 16));
                continue;
              } else {
                result += chr;
              }
            } else {
              return result;
            }
            pos++;
            chr = str.charAt(pos);
          }
          return result;
        };
        skipWhitespace = function() {
          chr = str.charAt(pos);
          var result = false;
          while (chr === ' ' || chr === '\t' || chr === '\n' || chr === '\r' || chr === '\f') {
            result = true;
            pos++;
            chr = str.charAt(pos);
          }
          return result;
        };
        this.parse = function() {
          var res = this.parseSelector();
          if (pos < l) {
            throw Error('Rule expected but "' + str.charAt(pos) + '" found.');
          }
          return res;
        };
        this.parseSelector = function() {
          var res;
          var selector = res = this.parseSingleSelector();
          chr = str.charAt(pos);
          while (chr === ',') {
            pos++;
            skipWhitespace();
            if (res.type !== 'selectors') {
              res = {
                type: 'selectors',
                selectors: [ selector ]
              };
            }
            selector = this.parseSingleSelector();
            if (!selector) {
              throw Error('Rule expected after ",".');
            }
            res.selectors.push(selector);
          }
          return res;
        };
        this.parseSingleSelector = function() {
          skipWhitespace();
          var selector = {
            type: 'ruleSet'
          };
          var rule = this.parseRule();
          if (!rule) {
            return null;
          }
          var currentRule = selector;
          while (rule) {
            rule.type = 'rule';
            currentRule.rule = rule;
            currentRule = rule;
            skipWhitespace();
            chr = str.charAt(pos);
            if (pos >= l || chr === ',' || chr === ')') {
              break;
            }
            if (ruleNestingOperators[chr]) {
              var op = chr;
              pos++;
              skipWhitespace();
              rule = this.parseRule();
              if (!rule) {
                throw Error('Rule expected after "' + op + '".');
              }
              rule.nestingOperator = op;
            } else {
              rule = this.parseRule();
              if (rule) {
                rule.nestingOperator = null;
              }
            }
          }
          return selector;
        };
        this.parseRule = function() {
          var rule = null;
          while (pos < l) {
            chr = str.charAt(pos);
            if (chr === '*') {
              pos++;
              (rule = rule || {}).tagName = '*';
            } else if (isIdentStart(chr) || chr === '\\') {
              (rule = rule || {}).tagName = getIdent();
            } else if (chr === '.') {
              pos++;
              rule = rule || {};
              (rule.classNames = rule.classNames || []).push(getIdent());
            } else if (chr === '#') {
              pos++;
              (rule = rule || {}).id = getIdent();
            } else if (chr === '[') {
              pos++;
              skipWhitespace();
              var attr = {
                name: getIdent()
              };
              skipWhitespace();
              if (chr === ']') {
                pos++;
              } else {
                var operator = '';
                if (attrEqualityMods[chr]) {
                  operator = chr;
                  pos++;
                  chr = str.charAt(pos);
                }
                if (pos >= l) {
                  throw Error('Expected "=" but end of file reached.');
                }
                if (chr !== '=') {
                  throw Error('Expected "=" but "' + chr + '" found.');
                }
                attr.operator = operator + '=';
                pos++;
                skipWhitespace();
                var attrValue = '';
                attr.valueType = 'string';
                if (chr === '"') {
                  attrValue = getStr('"', doubleQuotesEscapeChars);
                } else if (chr === '\'') {
                  attrValue = getStr('\'', singleQuoteEscapeChars);
                } else if (substitutesEnabled && chr === '$') {
                  pos++;
                  attrValue = getIdent();
                  attr.valueType = 'substitute';
                } else {
                  while (pos < l) {
                    if (chr === ']') {
                      break;
                    }
                    attrValue += chr;
                    pos++;
                    chr = str.charAt(pos);
                  }
                  attrValue = attrValue.trim();
                }
                skipWhitespace();
                if (pos >= l) {
                  throw Error('Expected "]" but end of file reached.');
                }
                if (chr !== ']') {
                  throw Error('Expected "]" but "' + chr + '" found.');
                }
                pos++;
                attr.value = attrValue;
              }
              rule = rule || {};
              (rule.attrs = rule.attrs || []).push(attr);
            } else if (chr === ':') {
              pos++;
              var pseudoName = getIdent();
              var pseudo = {
                name: pseudoName
              };
              if (chr === '(') {
                pos++;
                var value = '';
                skipWhitespace();
                if (pseudos[pseudoName] === 'selector') {
                  pseudo.valueType = 'selector';
                  value = this.parseSelector();
                } else {
                  pseudo.valueType = pseudos[pseudoName] || 'string';
                  if (chr === '"') {
                    value = getStr('"', doubleQuotesEscapeChars);
                  } else if (chr === '\'') {
                    value = getStr('\'', singleQuoteEscapeChars);
                  } else if (substitutesEnabled && chr === '$') {
                    pos++;
                    value = getIdent();
                    pseudo.valueType = 'substitute';
                  } else {
                    while (pos < l) {
                      if (chr === ')') {
                        break;
                      }
                      value += chr;
                      pos++;
                      chr = str.charAt(pos);
                    }
                    value = value.trim();
                  }
                  skipWhitespace();
                }
                if (pos >= l) {
                  throw Error('Expected ")" but end of file reached.');
                }
                if (chr !== ')') {
                  throw Error('Expected ")" but "' + chr + '" found.');
                }
                pos++;
                pseudo.value = value;
              }
              rule = rule || {};
              (rule.pseudos = rule.pseudos || []).push(pseudo);
            } else {
              break;
            }
          }
          return rule;
        };
        return this;
      }
      CssSelectorParser.prototype.parse = function(str) {
        var context = new ParseContext(str, 0, this.pseudos, this.attrEqualityMods, this.ruleNestingOperators, this.substitutesEnabled);
        return context.parse();
      };
      CssSelectorParser.prototype.escapeIdentifier = function(s) {
        var result = '';
        var i = 0;
        var len = s.length;
        while (i < len) {
          var chr = s.charAt(i);
          if (identSpecialChars[chr]) {
            result += '\\' + chr;
          } else {
            if (!(chr === '_' || chr === '-' || chr >= 'A' && chr <= 'Z' || chr >= 'a' && chr <= 'z' || i !== 0 && chr >= '0' && chr <= '9')) {
              var charCode = chr.charCodeAt(0);
              if ((charCode & 63488) === 55296) {
                var extraCharCode = s.charCodeAt(i++);
                if ((charCode & 64512) !== 55296 || (extraCharCode & 64512) !== 56320) {
                  throw Error('UCS-2(decode): illegal sequence');
                }
                charCode = ((charCode & 1023) << 10) + (extraCharCode & 1023) + 65536;
              }
              result += '\\' + charCode.toString(16) + ' ';
            } else {
              result += chr;
            }
          }
          i++;
        }
        return result;
      };
      CssSelectorParser.prototype.escapeStr = function(s) {
        var result = '';
        var i = 0;
        var len = s.length;
        var chr, replacement;
        while (i < len) {
          chr = s.charAt(i);
          if (chr === '"') {
            chr = '\\"';
          } else if (chr === '\\') {
            chr = '\\\\';
          } else if (replacement = strReplacementsRev[chr]) {
            chr = replacement;
          }
          result += chr;
          i++;
        }
        return '"' + result + '"';
      };
      CssSelectorParser.prototype.render = function(path) {
        return this._renderEntity(path).trim();
      };
      CssSelectorParser.prototype._renderEntity = function(entity) {
        var currentEntity, parts, res;
        res = '';
        switch (entity.type) {
         case 'ruleSet':
          currentEntity = entity.rule;
          parts = [];
          while (currentEntity) {
            if (currentEntity.nestingOperator) {
              parts.push(currentEntity.nestingOperator);
            }
            parts.push(this._renderEntity(currentEntity));
            currentEntity = currentEntity.rule;
          }
          res = parts.join(' ');
          break;

         case 'selectors':
          res = entity.selectors.map(this._renderEntity, this).join(', ');
          break;

         case 'rule':
          if (entity.tagName) {
            if (entity.tagName === '*') {
              res = '*';
            } else {
              res = this.escapeIdentifier(entity.tagName);
            }
          }
          if (entity.id) {
            res += '#' + this.escapeIdentifier(entity.id);
          }
          if (entity.classNames) {
            res += entity.classNames.map(function(cn) {
              return '.' + this.escapeIdentifier(cn);
            }, this).join('');
          }
          if (entity.attrs) {
            res += entity.attrs.map(function(attr) {
              if (attr.operator) {
                if (attr.valueType === 'substitute') {
                  return '[' + this.escapeIdentifier(attr.name) + attr.operator + '$' + attr.value + ']';
                } else {
                  return '[' + this.escapeIdentifier(attr.name) + attr.operator + this.escapeStr(attr.value) + ']';
                }
              } else {
                return '[' + this.escapeIdentifier(attr.name) + ']';
              }
            }, this).join('');
          }
          if (entity.pseudos) {
            res += entity.pseudos.map(function(pseudo) {
              if (pseudo.valueType) {
                if (pseudo.valueType === 'selector') {
                  return ':' + this.escapeIdentifier(pseudo.name) + '(' + this._renderEntity(pseudo.value) + ')';
                } else if (pseudo.valueType === 'substitute') {
                  return ':' + this.escapeIdentifier(pseudo.name) + '($' + pseudo.value + ')';
                } else if (pseudo.valueType === 'numeric') {
                  return ':' + this.escapeIdentifier(pseudo.name) + '(' + pseudo.value + ')';
                } else {
                  return ':' + this.escapeIdentifier(pseudo.name) + '(' + this.escapeIdentifier(pseudo.value) + ')';
                }
              } else {
                return ':' + this.escapeIdentifier(pseudo.name);
              }
            }, this).join('');
          }
          break;

         default:
          throw Error('Unknown entity type: "' + entity.type(+'".'));
        }
        return res;
      };
      exports.CssSelectorParser = CssSelectorParser;
    }, {} ],
    157: [ function(_dereq_, module, exports) {
      'use strict';
      var isValue = _dereq_('type/value/is'), isPlainFunction = _dereq_('type/plain-function/is'), assign = _dereq_('es5-ext/object/assign'), normalizeOpts = _dereq_('es5-ext/object/normalize-options'), contains = _dereq_('es5-ext/string/#/contains');
      var d = module.exports = function(dscr, value) {
        var c, e, w, options, desc;
        if (arguments.length < 2 || typeof dscr !== 'string') {
          options = value;
          value = dscr;
          dscr = null;
        } else {
          options = arguments[2];
        }
        if (isValue(dscr)) {
          c = contains.call(dscr, 'c');
          e = contains.call(dscr, 'e');
          w = contains.call(dscr, 'w');
        } else {
          c = w = true;
          e = false;
        }
        desc = {
          value: value,
          configurable: c,
          enumerable: e,
          writable: w
        };
        return !options ? desc : assign(normalizeOpts(options), desc);
      };
      d.gs = function(dscr, get, set) {
        var c, e, options, desc;
        if (typeof dscr !== 'string') {
          options = set;
          set = get;
          get = dscr;
          dscr = null;
        } else {
          options = arguments[3];
        }
        if (!isValue(get)) {
          get = undefined;
        } else if (!isPlainFunction(get)) {
          options = get;
          get = set = undefined;
        } else if (!isValue(set)) {
          set = undefined;
        } else if (!isPlainFunction(set)) {
          options = set;
          set = undefined;
        }
        if (isValue(dscr)) {
          c = contains.call(dscr, 'c');
          e = contains.call(dscr, 'e');
        } else {
          c = true;
          e = false;
        }
        desc = {
          get: get,
          set: set,
          configurable: c,
          enumerable: e
        };
        return !options ? desc : assign(normalizeOpts(options), desc);
      };
    }, {
      'es5-ext/object/assign': 178,
      'es5-ext/object/normalize-options': 190,
      'es5-ext/string/#/contains': 197,
      'type/plain-function/is': 242,
      'type/value/is': 244
    } ],
    158: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function() {
        return /\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62(?:\uDB40\uDC65\uDB40\uDC6E\uDB40\uDC67|\uDB40\uDC73\uDB40\uDC63\uDB40\uDC74|\uDB40\uDC77\uDB40\uDC6C\uDB40\uDC73)\uDB40\uDC7F|\uD83D\uDC68(?:\uD83C\uDFFC\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68\uD83C\uDFFB|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFE])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFE\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFD])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFC])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83D\uDC68|(?:\uD83D[\uDC68\uDC69])\u200D(?:\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67]))|\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67])|(?:\uD83D[\uDC68\uDC69])\u200D(?:\uD83D[\uDC66\uDC67])|[\u2695\u2696\u2708]\uFE0F|\uD83D[\uDC66\uDC67]|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|(?:\uD83C\uDFFB\u200D[\u2695\u2696\u2708]|\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708])\uFE0F|\uD83C\uDFFB\u200D(?:\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C[\uDFFB-\uDFFF])|(?:\uD83E\uDDD1\uD83C\uDFFB\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFC\u200D\uD83E\uDD1D\u200D\uD83D\uDC69)\uD83C\uDFFB|\uD83E\uDDD1(?:\uD83C\uDFFF\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1(?:\uD83C[\uDFFB-\uDFFF])|\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1)|(?:\uD83E\uDDD1\uD83C\uDFFE\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFF\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB-\uDFFE])|(?:\uD83E\uDDD1\uD83C\uDFFC\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFD\u200D\uD83E\uDD1D\u200D\uD83D\uDC69)(?:\uD83C[\uDFFB\uDFFC])|\uD83D\uDC69(?:\uD83C\uDFFE\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFD\uDFFF])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFC\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFD-\uDFFF])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFB\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFC-\uDFFF])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D(?:\uD83D[\uDC68\uDC69])|\uD83D[\uDC68\uDC69])|\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83C[\uDF3E\uDF73\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD]))|\uD83D\uDC69\u200D\uD83D\uDC69\u200D(?:\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67]))|(?:\uD83E\uDDD1\uD83C\uDFFD\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFE\u200D\uD83E\uDD1D\u200D\uD83D\uDC69)(?:\uD83C[\uDFFB-\uDFFD])|\uD83D\uDC69\u200D\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC69\u200D\uD83D\uDC69\u200D(?:\uD83D[\uDC66\uDC67])|(?:\uD83D\uDC41\uFE0F\u200D\uD83D\uDDE8|\uD83D\uDC69(?:\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708]|\uD83C\uDFFB\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\u200D[\u2695\u2696\u2708])|(?:(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)\uFE0F|\uD83D\uDC6F|\uD83E[\uDD3C\uDDDE\uDDDF])\u200D[\u2640\u2642]|(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)(?:\uD83C[\uDFFB-\uDFFF])\u200D[\u2640\u2642]|(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD6-\uDDDD])(?:(?:\uD83C[\uDFFB-\uDFFF])\u200D[\u2640\u2642]|\u200D[\u2640\u2642])|\uD83C\uDFF4\u200D\u2620)\uFE0F|\uD83D\uDC69\u200D\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67])|\uD83C\uDFF3\uFE0F\u200D\uD83C\uDF08|\uD83D\uDC15\u200D\uD83E\uDDBA|\uD83D\uDC69\u200D\uD83D\uDC66|\uD83D\uDC69\u200D\uD83D\uDC67|\uD83C\uDDFD\uD83C\uDDF0|\uD83C\uDDF4\uD83C\uDDF2|\uD83C\uDDF6\uD83C\uDDE6|[#\*0-9]\uFE0F\u20E3|\uD83C\uDDE7(?:\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEF\uDDF1-\uDDF4\uDDF6-\uDDF9\uDDFB\uDDFC\uDDFE\uDDFF])|\uD83C\uDDF9(?:\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDED\uDDEF-\uDDF4\uDDF7\uDDF9\uDDFB\uDDFC\uDDFF])|\uD83C\uDDEA(?:\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDED\uDDF7-\uDDFA])|\uD83E\uDDD1(?:\uD83C[\uDFFB-\uDFFF])|\uD83C\uDDF7(?:\uD83C[\uDDEA\uDDF4\uDDF8\uDDFA\uDDFC])|\uD83D\uDC69(?:\uD83C[\uDFFB-\uDFFF])|\uD83C\uDDF2(?:\uD83C[\uDDE6\uDDE8-\uDDED\uDDF0-\uDDFF])|\uD83C\uDDE6(?:\uD83C[\uDDE8-\uDDEC\uDDEE\uDDF1\uDDF2\uDDF4\uDDF6-\uDDFA\uDDFC\uDDFD\uDDFF])|\uD83C\uDDF0(?:\uD83C[\uDDEA\uDDEC-\uDDEE\uDDF2\uDDF3\uDDF5\uDDF7\uDDFC\uDDFE\uDDFF])|\uD83C\uDDED(?:\uD83C[\uDDF0\uDDF2\uDDF3\uDDF7\uDDF9\uDDFA])|\uD83C\uDDE9(?:\uD83C[\uDDEA\uDDEC\uDDEF\uDDF0\uDDF2\uDDF4\uDDFF])|\uD83C\uDDFE(?:\uD83C[\uDDEA\uDDF9])|\uD83C\uDDEC(?:\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEE\uDDF1-\uDDF3\uDDF5-\uDDFA\uDDFC\uDDFE])|\uD83C\uDDF8(?:\uD83C[\uDDE6-\uDDEA\uDDEC-\uDDF4\uDDF7-\uDDF9\uDDFB\uDDFD-\uDDFF])|\uD83C\uDDEB(?:\uD83C[\uDDEE-\uDDF0\uDDF2\uDDF4\uDDF7])|\uD83C\uDDF5(?:\uD83C[\uDDE6\uDDEA-\uDDED\uDDF0-\uDDF3\uDDF7-\uDDF9\uDDFC\uDDFE])|\uD83C\uDDFB(?:\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDEE\uDDF3\uDDFA])|\uD83C\uDDF3(?:\uD83C[\uDDE6\uDDE8\uDDEA-\uDDEC\uDDEE\uDDF1\uDDF4\uDDF5\uDDF7\uDDFA\uDDFF])|\uD83C\uDDE8(?:\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDEE\uDDF0-\uDDF5\uDDF7\uDDFA-\uDDFF])|\uD83C\uDDF1(?:\uD83C[\uDDE6-\uDDE8\uDDEE\uDDF0\uDDF7-\uDDFB\uDDFE])|\uD83C\uDDFF(?:\uD83C[\uDDE6\uDDF2\uDDFC])|\uD83C\uDDFC(?:\uD83C[\uDDEB\uDDF8])|\uD83C\uDDFA(?:\uD83C[\uDDE6\uDDEC\uDDF2\uDDF3\uDDF8\uDDFE\uDDFF])|\uD83C\uDDEE(?:\uD83C[\uDDE8-\uDDEA\uDDF1-\uDDF4\uDDF6-\uDDF9])|\uD83C\uDDEF(?:\uD83C[\uDDEA\uDDF2\uDDF4\uDDF5])|(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD6-\uDDDD])(?:\uD83C[\uDFFB-\uDFFF])|(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)(?:\uD83C[\uDFFB-\uDFFF])|(?:[\u261D\u270A-\u270D]|\uD83C[\uDF85\uDFC2\uDFC7]|\uD83D[\uDC42\uDC43\uDC46-\uDC50\uDC66\uDC67\uDC6B-\uDC6D\uDC70\uDC72\uDC74-\uDC76\uDC78\uDC7C\uDC83\uDC85\uDCAA\uDD74\uDD7A\uDD90\uDD95\uDD96\uDE4C\uDE4F\uDEC0\uDECC]|\uD83E[\uDD0F\uDD18-\uDD1C\uDD1E\uDD1F\uDD30-\uDD36\uDDB5\uDDB6\uDDBB\uDDD2-\uDDD5])(?:\uD83C[\uDFFB-\uDFFF])|(?:[\u231A\u231B\u23E9-\u23EC\u23F0\u23F3\u25FD\u25FE\u2614\u2615\u2648-\u2653\u267F\u2693\u26A1\u26AA\u26AB\u26BD\u26BE\u26C4\u26C5\u26CE\u26D4\u26EA\u26F2\u26F3\u26F5\u26FA\u26FD\u2705\u270A\u270B\u2728\u274C\u274E\u2753-\u2755\u2757\u2795-\u2797\u27B0\u27BF\u2B1B\u2B1C\u2B50\u2B55]|\uD83C[\uDC04\uDCCF\uDD8E\uDD91-\uDD9A\uDDE6-\uDDFF\uDE01\uDE1A\uDE2F\uDE32-\uDE36\uDE38-\uDE3A\uDE50\uDE51\uDF00-\uDF20\uDF2D-\uDF35\uDF37-\uDF7C\uDF7E-\uDF93\uDFA0-\uDFCA\uDFCF-\uDFD3\uDFE0-\uDFF0\uDFF4\uDFF8-\uDFFF]|\uD83D[\uDC00-\uDC3E\uDC40\uDC42-\uDCFC\uDCFF-\uDD3D\uDD4B-\uDD4E\uDD50-\uDD67\uDD7A\uDD95\uDD96\uDDA4\uDDFB-\uDE4F\uDE80-\uDEC5\uDECC\uDED0-\uDED2\uDED5\uDEEB\uDEEC\uDEF4-\uDEFA\uDFE0-\uDFEB]|\uD83E[\uDD0D-\uDD3A\uDD3C-\uDD45\uDD47-\uDD71\uDD73-\uDD76\uDD7A-\uDDA2\uDDA5-\uDDAA\uDDAE-\uDDCA\uDDCD-\uDDFF\uDE70-\uDE73\uDE78-\uDE7A\uDE80-\uDE82\uDE90-\uDE95])|(?:[#\*0-9\xA9\xAE\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9\u21AA\u231A\u231B\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615\u2618\u261D\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642\u2648-\u2653\u265F\u2660\u2663\u2665\u2666\u2668\u267B\u267E\u267F\u2692-\u2697\u2699\u269B\u269C\u26A0\u26A1\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5\u26C8\u26CE\u26CF\u26D1\u26D3\u26D4\u26E9\u26EA\u26F0-\u26F5\u26F7-\u26FA\u26FD\u2702\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728\u2733\u2734\u2744\u2747\u274C\u274E\u2753-\u2755\u2757\u2763\u2764\u2795-\u2797\u27A1\u27B0\u27BF\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299]|\uD83C[\uDC04\uDCCF\uDD70\uDD71\uDD7E\uDD7F\uDD8E\uDD91-\uDD9A\uDDE6-\uDDFF\uDE01\uDE02\uDE1A\uDE2F\uDE32-\uDE3A\uDE50\uDE51\uDF00-\uDF21\uDF24-\uDF93\uDF96\uDF97\uDF99-\uDF9B\uDF9E-\uDFF0\uDFF3-\uDFF5\uDFF7-\uDFFF]|\uD83D[\uDC00-\uDCFD\uDCFF-\uDD3D\uDD49-\uDD4E\uDD50-\uDD67\uDD6F\uDD70\uDD73-\uDD7A\uDD87\uDD8A-\uDD8D\uDD90\uDD95\uDD96\uDDA4\uDDA5\uDDA8\uDDB1\uDDB2\uDDBC\uDDC2-\uDDC4\uDDD1-\uDDD3\uDDDC-\uDDDE\uDDE1\uDDE3\uDDE8\uDDEF\uDDF3\uDDFA-\uDE4F\uDE80-\uDEC5\uDECB-\uDED2\uDED5\uDEE0-\uDEE5\uDEE9\uDEEB\uDEEC\uDEF0\uDEF3-\uDEFA\uDFE0-\uDFEB]|\uD83E[\uDD0D-\uDD3A\uDD3C-\uDD45\uDD47-\uDD71\uDD73-\uDD76\uDD7A-\uDDA2\uDDA5-\uDDAA\uDDAE-\uDDCA\uDDCD-\uDDFF\uDE70-\uDE73\uDE78-\uDE7A\uDE80-\uDE82\uDE90-\uDE95])\uFE0F|(?:[\u261D\u26F9\u270A-\u270D]|\uD83C[\uDF85\uDFC2-\uDFC4\uDFC7\uDFCA-\uDFCC]|\uD83D[\uDC42\uDC43\uDC46-\uDC50\uDC66-\uDC78\uDC7C\uDC81-\uDC83\uDC85-\uDC87\uDC8F\uDC91\uDCAA\uDD74\uDD75\uDD7A\uDD90\uDD95\uDD96\uDE45-\uDE47\uDE4B-\uDE4F\uDEA3\uDEB4-\uDEB6\uDEC0\uDECC]|\uD83E[\uDD0F\uDD18-\uDD1F\uDD26\uDD30-\uDD39\uDD3C-\uDD3E\uDDB5\uDDB6\uDDB8\uDDB9\uDDBB\uDDCD-\uDDCF\uDDD1-\uDDDD])/g;
      };
    }, {} ],
    159: [ function(_dereq_, module, exports) {
      'use strict';
      var numberIsNaN = _dereq_('../../number/is-nan'), toPosInt = _dereq_('../../number/to-pos-integer'), value = _dereq_('../../object/valid-value'), indexOf = Array.prototype.indexOf, objHasOwnProperty = Object.prototype.hasOwnProperty, abs = Math.abs, floor = Math.floor;
      module.exports = function(searchElement) {
        var i, length, fromIndex, val;
        if (!numberIsNaN(searchElement)) {
          return indexOf.apply(this, arguments);
        }
        length = toPosInt(value(this).length);
        fromIndex = arguments[1];
        if (isNaN(fromIndex)) {
          fromIndex = 0;
        } else if (fromIndex >= 0) {
          fromIndex = floor(fromIndex);
        } else {
          fromIndex = toPosInt(this.length) - floor(abs(fromIndex));
        }
        for (i = fromIndex; i < length; ++i) {
          if (objHasOwnProperty.call(this, i)) {
            val = this[i];
            if (numberIsNaN(val)) {
              return i;
            }
          }
        }
        return -1;
      };
    }, {
      '../../number/is-nan': 172,
      '../../number/to-pos-integer': 176,
      '../../object/valid-value': 193
    } ],
    160: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = _dereq_('./is-implemented')() ? Array.from : _dereq_('./shim');
    }, {
      './is-implemented': 161,
      './shim': 162
    } ],
    161: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function() {
        var from = Array.from, arr, result;
        if (typeof from !== 'function') {
          return false;
        }
        arr = [ 'raz', 'dwa' ];
        result = from(arr);
        return Boolean(result && result !== arr && result[1] === 'dwa');
      };
    }, {} ],
    162: [ function(_dereq_, module, exports) {
      'use strict';
      var iteratorSymbol = _dereq_('es6-symbol').iterator, isArguments = _dereq_('../../function/is-arguments'), isFunction = _dereq_('../../function/is-function'), toPosInt = _dereq_('../../number/to-pos-integer'), callable = _dereq_('../../object/valid-callable'), validValue = _dereq_('../../object/valid-value'), isValue = _dereq_('../../object/is-value'), isString = _dereq_('../../string/is-string'), isArray = Array.isArray, call = Function.prototype.call, desc = {
        configurable: true,
        enumerable: true,
        writable: true,
        value: null
      }, defineProperty = Object.defineProperty;
      module.exports = function(arrayLike) {
        var mapFn = arguments[1], thisArg = arguments[2], Context, i, j, arr, length, code, iterator, result, getIterator, value;
        arrayLike = Object(validValue(arrayLike));
        if (isValue(mapFn)) {
          callable(mapFn);
        }
        if (!this || this === Array || !isFunction(this)) {
          if (!mapFn) {
            if (isArguments(arrayLike)) {
              length = arrayLike.length;
              if (length !== 1) {
                return Array.apply(null, arrayLike);
              }
              arr = new Array(1);
              arr[0] = arrayLike[0];
              return arr;
            }
            if (isArray(arrayLike)) {
              arr = new Array(length = arrayLike.length);
              for (i = 0; i < length; ++i) {
                arr[i] = arrayLike[i];
              }
              return arr;
            }
          }
          arr = [];
        } else {
          Context = this;
        }
        if (!isArray(arrayLike)) {
          if ((getIterator = arrayLike[iteratorSymbol]) !== undefined) {
            iterator = callable(getIterator).call(arrayLike);
            if (Context) {
              arr = new Context();
            }
            result = iterator.next();
            i = 0;
            while (!result.done) {
              value = mapFn ? call.call(mapFn, thisArg, result.value, i) : result.value;
              if (Context) {
                desc.value = value;
                defineProperty(arr, i, desc);
              } else {
                arr[i] = value;
              }
              result = iterator.next();
              ++i;
            }
            length = i;
          } else if (isString(arrayLike)) {
            length = arrayLike.length;
            if (Context) {
              arr = new Context();
            }
            for (i = 0, j = 0; i < length; ++i) {
              value = arrayLike[i];
              if (i + 1 < length) {
                code = value.charCodeAt(0);
                if (code >= 55296 && code <= 56319) {
                  value += arrayLike[++i];
                }
              }
              value = mapFn ? call.call(mapFn, thisArg, value, j) : value;
              if (Context) {
                desc.value = value;
                defineProperty(arr, j, desc);
              } else {
                arr[j] = value;
              }
              ++j;
            }
            length = j;
          }
        }
        if (length === undefined) {
          length = toPosInt(arrayLike.length);
          if (Context) {
            arr = new Context(length);
          }
          for (i = 0; i < length; ++i) {
            value = mapFn ? call.call(mapFn, thisArg, arrayLike[i], i) : arrayLike[i];
            if (Context) {
              desc.value = value;
              defineProperty(arr, i, desc);
            } else {
              arr[i] = value;
            }
          }
        }
        if (Context) {
          desc.value = null;
          arr.length = length;
        }
        return arr;
      };
    }, {
      '../../function/is-arguments': 166,
      '../../function/is-function': 167,
      '../../number/to-pos-integer': 176,
      '../../object/is-value': 184,
      '../../object/valid-callable': 192,
      '../../object/valid-value': 193,
      '../../string/is-string': 200,
      'es6-symbol': 203
    } ],
    163: [ function(_dereq_, module, exports) {
      'use strict';
      var from = _dereq_('./from'), isArray = Array.isArray;
      module.exports = function(arrayLike) {
        return isArray(arrayLike) ? arrayLike : from(arrayLike);
      };
    }, {
      './from': 160
    } ],
    164: [ function(_dereq_, module, exports) {
      'use strict';
      var assign = _dereq_('../object/assign'), isObject = _dereq_('../object/is-object'), isValue = _dereq_('../object/is-value'), captureStackTrace = Error.captureStackTrace;
      module.exports = function(message) {
        var err = new Error(message), code = arguments[1], ext = arguments[2];
        if (!isValue(ext)) {
          if (isObject(code)) {
            ext = code;
            code = null;
          }
        }
        if (isValue(ext)) {
          assign(err, ext);
        }
        if (isValue(code)) {
          err.code = code;
        }
        if (captureStackTrace) {
          captureStackTrace(err, module.exports);
        }
        return err;
      };
    }, {
      '../object/assign': 178,
      '../object/is-object': 183,
      '../object/is-value': 184
    } ],
    165: [ function(_dereq_, module, exports) {
      'use strict';
      var toPosInt = _dereq_('../number/to-pos-integer');
      var test = function(arg1, arg2) {
        return arg2;
      };
      var desc, defineProperty, generate, mixin;
      try {
        Object.defineProperty(test, 'length', {
          configurable: true,
          writable: false,
          enumerable: false,
          value: 1
        });
      } catch (ignore) {}
      if (test.length === 1) {
        desc = {
          configurable: true,
          writable: false,
          enumerable: false
        };
        defineProperty = Object.defineProperty;
        module.exports = function(fn, length) {
          length = toPosInt(length);
          if (fn.length === length) {
            return fn;
          }
          desc.value = length;
          return defineProperty(fn, 'length', desc);
        };
      } else {
        mixin = _dereq_('../object/mixin');
        generate = function() {
          var cache = [];
          return function(length) {
            var args, i = 0;
            if (cache[length]) {
              return cache[length];
            }
            args = [];
            while (length--) {
              args.push('a' + (++i).toString(36));
            }
            return new Function('fn', 'return function (' + args.join(', ') + ') { return fn.apply(this, arguments); };');
          };
        }();
        module.exports = function(src, length) {
          var target;
          length = toPosInt(length);
          if (src.length === length) {
            return src;
          }
          target = generate(length)(src);
          try {
            mixin(target, src);
          } catch (ignore) {}
          return target;
        };
      }
    }, {
      '../number/to-pos-integer': 176,
      '../object/mixin': 189
    } ],
    166: [ function(_dereq_, module, exports) {
      'use strict';
      var objToString = Object.prototype.toString, id = objToString.call(function() {
        return arguments;
      }());
      module.exports = function(value) {
        return objToString.call(value) === id;
      };
    }, {} ],
    167: [ function(_dereq_, module, exports) {
      'use strict';
      var objToString = Object.prototype.toString, isFunctionStringTag = RegExp.prototype.test.bind(/^[object [A-Za-z0-9]*Function]$/);
      module.exports = function(value) {
        return typeof value === 'function' && isFunctionStringTag(objToString.call(value));
      };
    }, {} ],
    168: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function() {};
    }, {} ],
    169: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = _dereq_('./is-implemented')() ? Math.sign : _dereq_('./shim');
    }, {
      './is-implemented': 170,
      './shim': 171
    } ],
    170: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function() {
        var sign = Math.sign;
        if (typeof sign !== 'function') {
          return false;
        }
        return sign(10) === 1 && sign(-20) === -1;
      };
    }, {} ],
    171: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function(value) {
        value = Number(value);
        if (isNaN(value) || value === 0) {
          return value;
        }
        return value > 0 ? 1 : -1;
      };
    }, {} ],
    172: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = _dereq_('./is-implemented')() ? Number.isNaN : _dereq_('./shim');
    }, {
      './is-implemented': 173,
      './shim': 174
    } ],
    173: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function() {
        var numberIsNaN = Number.isNaN;
        if (typeof numberIsNaN !== 'function') {
          return false;
        }
        return !numberIsNaN({}) && numberIsNaN(NaN) && !numberIsNaN(34);
      };
    }, {} ],
    174: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function(value) {
        return value !== value;
      };
    }, {} ],
    175: [ function(_dereq_, module, exports) {
      'use strict';
      var sign = _dereq_('../math/sign'), abs = Math.abs, floor = Math.floor;
      module.exports = function(value) {
        if (isNaN(value)) {
          return 0;
        }
        value = Number(value);
        if (value === 0 || !isFinite(value)) {
          return value;
        }
        return sign(value) * floor(abs(value));
      };
    }, {
      '../math/sign': 169
    } ],
    176: [ function(_dereq_, module, exports) {
      'use strict';
      var toInteger = _dereq_('./to-integer'), max = Math.max;
      module.exports = function(value) {
        return max(0, toInteger(value));
      };
    }, {
      './to-integer': 175
    } ],
    177: [ function(_dereq_, module, exports) {
      'use strict';
      var callable = _dereq_('./valid-callable'), value = _dereq_('./valid-value'), bind = Function.prototype.bind, call = Function.prototype.call, keys = Object.keys, objPropertyIsEnumerable = Object.prototype.propertyIsEnumerable;
      module.exports = function(method, defVal) {
        return function(obj, cb) {
          var list, thisArg = arguments[2], compareFn = arguments[3];
          obj = Object(value(obj));
          callable(cb);
          list = keys(obj);
          if (compareFn) {
            list.sort(typeof compareFn === 'function' ? bind.call(compareFn, obj) : undefined);
          }
          if (typeof method !== 'function') {
            method = list[method];
          }
          return call.call(method, list, function(key, index) {
            if (!objPropertyIsEnumerable.call(obj, key)) {
              return defVal;
            }
            return call.call(cb, thisArg, obj[key], key, obj, index);
          });
        };
      };
    }, {
      './valid-callable': 192,
      './valid-value': 193
    } ],
    178: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = _dereq_('./is-implemented')() ? Object.assign : _dereq_('./shim');
    }, {
      './is-implemented': 179,
      './shim': 180
    } ],
    179: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function() {
        var assign = Object.assign, obj;
        if (typeof assign !== 'function') {
          return false;
        }
        obj = {
          foo: 'raz'
        };
        assign(obj, {
          bar: 'dwa'
        }, {
          trzy: 'trzy'
        });
        return obj.foo + obj.bar + obj.trzy === 'razdwatrzy';
      };
    }, {} ],
    180: [ function(_dereq_, module, exports) {
      'use strict';
      var keys = _dereq_('../keys'), value = _dereq_('../valid-value'), max = Math.max;
      module.exports = function(dest, src) {
        var error, i, length = max(arguments.length, 2), assign;
        dest = Object(value(dest));
        assign = function(key) {
          try {
            dest[key] = src[key];
          } catch (e) {
            if (!error) {
              error = e;
            }
          }
        };
        for (i = 1; i < length; ++i) {
          src = arguments[i];
          keys(src).forEach(assign);
        }
        if (error !== undefined) {
          throw error;
        }
        return dest;
      };
    }, {
      '../keys': 185,
      '../valid-value': 193
    } ],
    181: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = _dereq_('./_iterate')('forEach');
    }, {
      './_iterate': 177
    } ],
    182: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function(obj) {
        return typeof obj === 'function';
      };
    }, {} ],
    183: [ function(_dereq_, module, exports) {
      'use strict';
      var isValue = _dereq_('./is-value');
      var map = {
        function: true,
        object: true
      };
      module.exports = function(value) {
        return isValue(value) && map[typeof value] || false;
      };
    }, {
      './is-value': 184
    } ],
    184: [ function(_dereq_, module, exports) {
      'use strict';
      var _undefined = _dereq_('../function/noop')();
      module.exports = function(val) {
        return val !== _undefined && val !== null;
      };
    }, {
      '../function/noop': 168
    } ],
    185: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = _dereq_('./is-implemented')() ? Object.keys : _dereq_('./shim');
    }, {
      './is-implemented': 186,
      './shim': 187
    } ],
    186: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function() {
        try {
          Object.keys('primitive');
          return true;
        } catch (e) {
          return false;
        }
      };
    }, {} ],
    187: [ function(_dereq_, module, exports) {
      'use strict';
      var isValue = _dereq_('../is-value');
      var keys = Object.keys;
      module.exports = function(object) {
        return keys(isValue(object) ? Object(object) : object);
      };
    }, {
      '../is-value': 184
    } ],
    188: [ function(_dereq_, module, exports) {
      'use strict';
      var callable = _dereq_('./valid-callable'), forEach = _dereq_('./for-each'), call = Function.prototype.call;
      module.exports = function(obj, cb) {
        var result = {}, thisArg = arguments[2];
        callable(cb);
        forEach(obj, function(value, key, targetObj, index) {
          result[key] = call.call(cb, thisArg, value, key, targetObj, index);
        });
        return result;
      };
    }, {
      './for-each': 181,
      './valid-callable': 192
    } ],
    189: [ function(_dereq_, module, exports) {
      'use strict';
      var value = _dereq_('./valid-value'), defineProperty = Object.defineProperty, getOwnPropertyDescriptor = Object.getOwnPropertyDescriptor, getOwnPropertyNames = Object.getOwnPropertyNames, getOwnPropertySymbols = Object.getOwnPropertySymbols;
      module.exports = function(target, source) {
        var error, sourceObject = Object(value(source));
        target = Object(value(target));
        getOwnPropertyNames(sourceObject).forEach(function(name) {
          try {
            defineProperty(target, name, getOwnPropertyDescriptor(source, name));
          } catch (e) {
            error = e;
          }
        });
        if (typeof getOwnPropertySymbols === 'function') {
          getOwnPropertySymbols(sourceObject).forEach(function(symbol) {
            try {
              defineProperty(target, symbol, getOwnPropertyDescriptor(source, symbol));
            } catch (e) {
              error = e;
            }
          });
        }
        if (error !== undefined) {
          throw error;
        }
        return target;
      };
    }, {
      './valid-value': 193
    } ],
    190: [ function(_dereq_, module, exports) {
      'use strict';
      var isValue = _dereq_('./is-value');
      var forEach = Array.prototype.forEach, create = Object.create;
      var process = function(src, obj) {
        var key;
        for (key in src) {
          obj[key] = src[key];
        }
      };
      module.exports = function(opts1) {
        var result = create(null);
        forEach.call(arguments, function(options) {
          if (!isValue(options)) {
            return;
          }
          process(Object(options), result);
        });
        return result;
      };
    }, {
      './is-value': 184
    } ],
    191: [ function(_dereq_, module, exports) {
      'use strict';
      var forEach = Array.prototype.forEach, create = Object.create;
      module.exports = function(arg) {
        var set = create(null);
        forEach.call(arguments, function(name) {
          set[name] = true;
        });
        return set;
      };
    }, {} ],
    192: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function(fn) {
        if (typeof fn !== 'function') {
          throw new TypeError(fn + ' is not a function');
        }
        return fn;
      };
    }, {} ],
    193: [ function(_dereq_, module, exports) {
      'use strict';
      var isValue = _dereq_('./is-value');
      module.exports = function(value) {
        if (!isValue(value)) {
          throw new TypeError('Cannot use null or undefined');
        }
        return value;
      };
    }, {
      './is-value': 184
    } ],
    194: [ function(_dereq_, module, exports) {
      'use strict';
      var ensureValue = _dereq_('./valid-value'), stringifiable = _dereq_('./validate-stringifiable');
      module.exports = function(value) {
        return stringifiable(ensureValue(value));
      };
    }, {
      './valid-value': 193,
      './validate-stringifiable': 195
    } ],
    195: [ function(_dereq_, module, exports) {
      'use strict';
      var isCallable = _dereq_('./is-callable');
      module.exports = function(stringifiable) {
        try {
          if (stringifiable && isCallable(stringifiable.toString)) {
            return stringifiable.toString();
          }
          return String(stringifiable);
        } catch (e) {
          throw new TypeError('Passed argument cannot be stringifed');
        }
      };
    }, {
      './is-callable': 182
    } ],
    196: [ function(_dereq_, module, exports) {
      'use strict';
      var isCallable = _dereq_('./object/is-callable');
      module.exports = function(value) {
        try {
          if (value && isCallable(value.toString)) {
            return value.toString();
          }
          return String(value);
        } catch (e) {
          return '<Non-coercible to string value>';
        }
      };
    }, {
      './object/is-callable': 182
    } ],
    197: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = _dereq_('./is-implemented')() ? String.prototype.contains : _dereq_('./shim');
    }, {
      './is-implemented': 198,
      './shim': 199
    } ],
    198: [ function(_dereq_, module, exports) {
      'use strict';
      var str = 'razdwatrzy';
      module.exports = function() {
        if (typeof str.contains !== 'function') {
          return false;
        }
        return str.contains('dwa') === true && str.contains('foo') === false;
      };
    }, {} ],
    199: [ function(_dereq_, module, exports) {
      'use strict';
      var indexOf = String.prototype.indexOf;
      module.exports = function(searchString) {
        return indexOf.call(this, searchString, arguments[1]) > -1;
      };
    }, {} ],
    200: [ function(_dereq_, module, exports) {
      'use strict';
      var objToString = Object.prototype.toString, id = objToString.call('');
      module.exports = function(value) {
        return typeof value === 'string' || value && typeof value === 'object' && (value instanceof String || objToString.call(value) === id) || false;
      };
    }, {} ],
    201: [ function(_dereq_, module, exports) {
      'use strict';
      var safeToString = _dereq_('./safe-to-string');
      var reNewLine = /[\n\r\u2028\u2029]/g;
      module.exports = function(value) {
        var string = safeToString(value);
        if (string.length > 100) {
          string = string.slice(0, 99) + '\u2026';
        }
        string = string.replace(reNewLine, function(char) {
          return JSON.stringify(char).slice(1, -1);
        });
        return string;
      };
    }, {
      './safe-to-string': 196
    } ],
    202: [ function(_dereq_, module, exports) {
      (function(process, global) {
        (function(global, factory) {
          typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory() : typeof define === 'function' && define.amd ? define(factory) : global.ES6Promise = factory();
        })(this, function() {
          'use strict';
          function objectOrFunction(x) {
            var type = typeof x;
            return x !== null && (type === 'object' || type === 'function');
          }
          function isFunction(x) {
            return typeof x === 'function';
          }
          var _isArray = void 0;
          if (Array.isArray) {
            _isArray = Array.isArray;
          } else {
            _isArray = function(x) {
              return Object.prototype.toString.call(x) === '[object Array]';
            };
          }
          var isArray = _isArray;
          var len = 0;
          var vertxNext = void 0;
          var customSchedulerFn = void 0;
          var asap = function asap(callback, arg) {
            queue[len] = callback;
            queue[len + 1] = arg;
            len += 2;
            if (len === 2) {
              if (customSchedulerFn) {
                customSchedulerFn(flush);
              } else {
                scheduleFlush();
              }
            }
          };
          function setScheduler(scheduleFn) {
            customSchedulerFn = scheduleFn;
          }
          function setAsap(asapFn) {
            asap = asapFn;
          }
          var browserWindow = typeof window !== 'undefined' ? window : undefined;
          var browserGlobal = browserWindow || {};
          var BrowserMutationObserver = browserGlobal.MutationObserver || browserGlobal.WebKitMutationObserver;
          var isNode = typeof self === 'undefined' && typeof process !== 'undefined' && {}.toString.call(process) === '[object process]';
          var isWorker = typeof Uint8ClampedArray !== 'undefined' && typeof importScripts !== 'undefined' && typeof MessageChannel !== 'undefined';
          function useNextTick() {
            return function() {
              return process.nextTick(flush);
            };
          }
          function useVertxTimer() {
            if (typeof vertxNext !== 'undefined') {
              return function() {
                vertxNext(flush);
              };
            }
            return useSetTimeout();
          }
          function useMutationObserver() {
            var iterations = 0;
            var observer = new BrowserMutationObserver(flush);
            var node = document.createTextNode('');
            observer.observe(node, {
              characterData: true
            });
            return function() {
              node.data = iterations = ++iterations % 2;
            };
          }
          function useMessageChannel() {
            var channel = new MessageChannel();
            channel.port1.onmessage = flush;
            return function() {
              return channel.port2.postMessage(0);
            };
          }
          function useSetTimeout() {
            var globalSetTimeout = setTimeout;
            return function() {
              return globalSetTimeout(flush, 1);
            };
          }
          var queue = new Array(1e3);
          function flush() {
            for (var i = 0; i < len; i += 2) {
              var callback = queue[i];
              var arg = queue[i + 1];
              callback(arg);
              queue[i] = undefined;
              queue[i + 1] = undefined;
            }
            len = 0;
          }
          function attemptVertx() {
            try {
              var vertx = Function('return this')().require('vertx');
              vertxNext = vertx.runOnLoop || vertx.runOnContext;
              return useVertxTimer();
            } catch (e) {
              return useSetTimeout();
            }
          }
          var scheduleFlush = void 0;
          if (isNode) {
            scheduleFlush = useNextTick();
          } else if (BrowserMutationObserver) {
            scheduleFlush = useMutationObserver();
          } else if (isWorker) {
            scheduleFlush = useMessageChannel();
          } else if (browserWindow === undefined && typeof _dereq_ === 'function') {
            scheduleFlush = attemptVertx();
          } else {
            scheduleFlush = useSetTimeout();
          }
          function then(onFulfillment, onRejection) {
            var parent = this;
            var child = new this.constructor(noop);
            if (child[PROMISE_ID] === undefined) {
              makePromise(child);
            }
            var _state = parent._state;
            if (_state) {
              var callback = arguments[_state - 1];
              asap(function() {
                return invokeCallback(_state, child, callback, parent._result);
              });
            } else {
              subscribe(parent, child, onFulfillment, onRejection);
            }
            return child;
          }
          function resolve$1(object) {
            var Constructor = this;
            if (object && typeof object === 'object' && object.constructor === Constructor) {
              return object;
            }
            var promise = new Constructor(noop);
            resolve(promise, object);
            return promise;
          }
          var PROMISE_ID = Math.random().toString(36).substring(2);
          function noop() {}
          var PENDING = void 0;
          var FULFILLED = 1;
          var REJECTED = 2;
          function selfFulfillment() {
            return new TypeError('You cannot resolve a promise with itself');
          }
          function cannotReturnOwn() {
            return new TypeError('A promises callback cannot return that same promise.');
          }
          function tryThen(then$$1, value, fulfillmentHandler, rejectionHandler) {
            try {
              then$$1.call(value, fulfillmentHandler, rejectionHandler);
            } catch (e) {
              return e;
            }
          }
          function handleForeignThenable(promise, thenable, then$$1) {
            asap(function(promise) {
              var sealed = false;
              var error = tryThen(then$$1, thenable, function(value) {
                if (sealed) {
                  return;
                }
                sealed = true;
                if (thenable !== value) {
                  resolve(promise, value);
                } else {
                  fulfill(promise, value);
                }
              }, function(reason) {
                if (sealed) {
                  return;
                }
                sealed = true;
                reject(promise, reason);
              }, 'Settle: ' + (promise._label || ' unknown promise'));
              if (!sealed && error) {
                sealed = true;
                reject(promise, error);
              }
            }, promise);
          }
          function handleOwnThenable(promise, thenable) {
            if (thenable._state === FULFILLED) {
              fulfill(promise, thenable._result);
            } else if (thenable._state === REJECTED) {
              reject(promise, thenable._result);
            } else {
              subscribe(thenable, undefined, function(value) {
                return resolve(promise, value);
              }, function(reason) {
                return reject(promise, reason);
              });
            }
          }
          function handleMaybeThenable(promise, maybeThenable, then$$1) {
            if (maybeThenable.constructor === promise.constructor && then$$1 === then && maybeThenable.constructor.resolve === resolve$1) {
              handleOwnThenable(promise, maybeThenable);
            } else {
              if (then$$1 === undefined) {
                fulfill(promise, maybeThenable);
              } else if (isFunction(then$$1)) {
                handleForeignThenable(promise, maybeThenable, then$$1);
              } else {
                fulfill(promise, maybeThenable);
              }
            }
          }
          function resolve(promise, value) {
            if (promise === value) {
              reject(promise, selfFulfillment());
            } else if (objectOrFunction(value)) {
              var then$$1 = void 0;
              try {
                then$$1 = value.then;
              } catch (error) {
                reject(promise, error);
                return;
              }
              handleMaybeThenable(promise, value, then$$1);
            } else {
              fulfill(promise, value);
            }
          }
          function publishRejection(promise) {
            if (promise._onerror) {
              promise._onerror(promise._result);
            }
            publish(promise);
          }
          function fulfill(promise, value) {
            if (promise._state !== PENDING) {
              return;
            }
            promise._result = value;
            promise._state = FULFILLED;
            if (promise._subscribers.length !== 0) {
              asap(publish, promise);
            }
          }
          function reject(promise, reason) {
            if (promise._state !== PENDING) {
              return;
            }
            promise._state = REJECTED;
            promise._result = reason;
            asap(publishRejection, promise);
          }
          function subscribe(parent, child, onFulfillment, onRejection) {
            var _subscribers = parent._subscribers;
            var length = _subscribers.length;
            parent._onerror = null;
            _subscribers[length] = child;
            _subscribers[length + FULFILLED] = onFulfillment;
            _subscribers[length + REJECTED] = onRejection;
            if (length === 0 && parent._state) {
              asap(publish, parent);
            }
          }
          function publish(promise) {
            var subscribers = promise._subscribers;
            var settled = promise._state;
            if (subscribers.length === 0) {
              return;
            }
            var child = void 0, callback = void 0, detail = promise._result;
            for (var i = 0; i < subscribers.length; i += 3) {
              child = subscribers[i];
              callback = subscribers[i + settled];
              if (child) {
                invokeCallback(settled, child, callback, detail);
              } else {
                callback(detail);
              }
            }
            promise._subscribers.length = 0;
          }
          function invokeCallback(settled, promise, callback, detail) {
            var hasCallback = isFunction(callback), value = void 0, error = void 0, succeeded = true;
            if (hasCallback) {
              try {
                value = callback(detail);
              } catch (e) {
                succeeded = false;
                error = e;
              }
              if (promise === value) {
                reject(promise, cannotReturnOwn());
                return;
              }
            } else {
              value = detail;
            }
            if (promise._state !== PENDING) {} else if (hasCallback && succeeded) {
              resolve(promise, value);
            } else if (succeeded === false) {
              reject(promise, error);
            } else if (settled === FULFILLED) {
              fulfill(promise, value);
            } else if (settled === REJECTED) {
              reject(promise, value);
            }
          }
          function initializePromise(promise, resolver) {
            try {
              resolver(function resolvePromise(value) {
                resolve(promise, value);
              }, function rejectPromise(reason) {
                reject(promise, reason);
              });
            } catch (e) {
              reject(promise, e);
            }
          }
          var id = 0;
          function nextId() {
            return id++;
          }
          function makePromise(promise) {
            promise[PROMISE_ID] = id++;
            promise._state = undefined;
            promise._result = undefined;
            promise._subscribers = [];
          }
          function validationError() {
            return new Error('Array Methods must be provided an Array');
          }
          var Enumerator = function() {
            function Enumerator(Constructor, input) {
              this._instanceConstructor = Constructor;
              this.promise = new Constructor(noop);
              if (!this.promise[PROMISE_ID]) {
                makePromise(this.promise);
              }
              if (isArray(input)) {
                this.length = input.length;
                this._remaining = input.length;
                this._result = new Array(this.length);
                if (this.length === 0) {
                  fulfill(this.promise, this._result);
                } else {
                  this.length = this.length || 0;
                  this._enumerate(input);
                  if (this._remaining === 0) {
                    fulfill(this.promise, this._result);
                  }
                }
              } else {
                reject(this.promise, validationError());
              }
            }
            Enumerator.prototype._enumerate = function _enumerate(input) {
              for (var i = 0; this._state === PENDING && i < input.length; i++) {
                this._eachEntry(input[i], i);
              }
            };
            Enumerator.prototype._eachEntry = function _eachEntry(entry, i) {
              var c = this._instanceConstructor;
              var resolve$$1 = c.resolve;
              if (resolve$$1 === resolve$1) {
                var _then = void 0;
                var error = void 0;
                var didError = false;
                try {
                  _then = entry.then;
                } catch (e) {
                  didError = true;
                  error = e;
                }
                if (_then === then && entry._state !== PENDING) {
                  this._settledAt(entry._state, i, entry._result);
                } else if (typeof _then !== 'function') {
                  this._remaining--;
                  this._result[i] = entry;
                } else if (c === Promise$1) {
                  var promise = new c(noop);
                  if (didError) {
                    reject(promise, error);
                  } else {
                    handleMaybeThenable(promise, entry, _then);
                  }
                  this._willSettleAt(promise, i);
                } else {
                  this._willSettleAt(new c(function(resolve$$1) {
                    return resolve$$1(entry);
                  }), i);
                }
              } else {
                this._willSettleAt(resolve$$1(entry), i);
              }
            };
            Enumerator.prototype._settledAt = function _settledAt(state, i, value) {
              var promise = this.promise;
              if (promise._state === PENDING) {
                this._remaining--;
                if (state === REJECTED) {
                  reject(promise, value);
                } else {
                  this._result[i] = value;
                }
              }
              if (this._remaining === 0) {
                fulfill(promise, this._result);
              }
            };
            Enumerator.prototype._willSettleAt = function _willSettleAt(promise, i) {
              var enumerator = this;
              subscribe(promise, undefined, function(value) {
                return enumerator._settledAt(FULFILLED, i, value);
              }, function(reason) {
                return enumerator._settledAt(REJECTED, i, reason);
              });
            };
            return Enumerator;
          }();
          function all(entries) {
            return new Enumerator(this, entries).promise;
          }
          function race(entries) {
            var Constructor = this;
            if (!isArray(entries)) {
              return new Constructor(function(_, reject) {
                return reject(new TypeError('You must pass an array to race.'));
              });
            } else {
              return new Constructor(function(resolve, reject) {
                var length = entries.length;
                for (var i = 0; i < length; i++) {
                  Constructor.resolve(entries[i]).then(resolve, reject);
                }
              });
            }
          }
          function reject$1(reason) {
            var Constructor = this;
            var promise = new Constructor(noop);
            reject(promise, reason);
            return promise;
          }
          function needsResolver() {
            throw new TypeError('You must pass a resolver function as the first argument to the promise constructor');
          }
          function needsNew() {
            throw new TypeError('Failed to construct \'Promise\': Please use the \'new\' operator, this object constructor cannot be called as a function.');
          }
          var Promise$1 = function() {
            function Promise(resolver) {
              this[PROMISE_ID] = nextId();
              this._result = this._state = undefined;
              this._subscribers = [];
              if (noop !== resolver) {
                typeof resolver !== 'function' && needsResolver();
                this instanceof Promise ? initializePromise(this, resolver) : needsNew();
              }
            }
            Promise.prototype.catch = function _catch(onRejection) {
              return this.then(null, onRejection);
            };
            Promise.prototype.finally = function _finally(callback) {
              var promise = this;
              var constructor = promise.constructor;
              if (isFunction(callback)) {
                return promise.then(function(value) {
                  return constructor.resolve(callback()).then(function() {
                    return value;
                  });
                }, function(reason) {
                  return constructor.resolve(callback()).then(function() {
                    throw reason;
                  });
                });
              }
              return promise.then(callback, callback);
            };
            return Promise;
          }();
          Promise$1.prototype.then = then;
          Promise$1.all = all;
          Promise$1.race = race;
          Promise$1.resolve = resolve$1;
          Promise$1.reject = reject$1;
          Promise$1._setScheduler = setScheduler;
          Promise$1._setAsap = setAsap;
          Promise$1._asap = asap;
          function polyfill() {
            var local = void 0;
            if (typeof global !== 'undefined') {
              local = global;
            } else if (typeof self !== 'undefined') {
              local = self;
            } else {
              try {
                local = Function('return this')();
              } catch (e) {
                throw new Error('polyfill failed because global object is unavailable in this environment');
              }
            }
            var P = local.Promise;
            if (P) {
              var promiseToString = null;
              try {
                promiseToString = Object.prototype.toString.call(P.resolve());
              } catch (e) {}
              if (promiseToString === '[object Promise]' && !P.cast) {
                return;
              }
            }
            local.Promise = Promise$1;
          }
          Promise$1.polyfill = polyfill;
          Promise$1.Promise = Promise$1;
          return Promise$1;
        });
      }).call(this, _dereq_('_process'), typeof global !== 'undefined' ? global : typeof self !== 'undefined' ? self : typeof window !== 'undefined' ? window : {});
    }, {
      _process: 236
    } ],
    203: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = _dereq_('./is-implemented')() ? _dereq_('ext/global-this').Symbol : _dereq_('./polyfill');
    }, {
      './is-implemented': 204,
      './polyfill': 209,
      'ext/global-this': 213
    } ],
    204: [ function(_dereq_, module, exports) {
      'use strict';
      var global = _dereq_('ext/global-this'), validTypes = {
        object: true,
        symbol: true
      };
      module.exports = function() {
        var Symbol = global.Symbol;
        var symbol;
        if (typeof Symbol !== 'function') {
          return false;
        }
        symbol = Symbol('test symbol');
        try {
          String(symbol);
        } catch (e) {
          return false;
        }
        if (!validTypes[typeof Symbol.iterator]) {
          return false;
        }
        if (!validTypes[typeof Symbol.toPrimitive]) {
          return false;
        }
        if (!validTypes[typeof Symbol.toStringTag]) {
          return false;
        }
        return true;
      };
    }, {
      'ext/global-this': 213
    } ],
    205: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function(value) {
        if (!value) {
          return false;
        }
        if (typeof value === 'symbol') {
          return true;
        }
        if (!value.constructor) {
          return false;
        }
        if (value.constructor.name !== 'Symbol') {
          return false;
        }
        return value[value.constructor.toStringTag] === 'Symbol';
      };
    }, {} ],
    206: [ function(_dereq_, module, exports) {
      'use strict';
      var d = _dereq_('d');
      var create = Object.create, defineProperty = Object.defineProperty, objPrototype = Object.prototype;
      var created = create(null);
      module.exports = function(desc) {
        var postfix = 0, name, ie11BugWorkaround;
        while (created[desc + (postfix || '')]) {
          ++postfix;
        }
        desc += postfix || '';
        created[desc] = true;
        name = '@@' + desc;
        defineProperty(objPrototype, name, d.gs(null, function(value) {
          if (ie11BugWorkaround) {
            return;
          }
          ie11BugWorkaround = true;
          defineProperty(this, name, d(value));
          ie11BugWorkaround = false;
        }));
        return name;
      };
    }, {
      d: 157
    } ],
    207: [ function(_dereq_, module, exports) {
      'use strict';
      var d = _dereq_('d'), NativeSymbol = _dereq_('ext/global-this').Symbol;
      module.exports = function(SymbolPolyfill) {
        return Object.defineProperties(SymbolPolyfill, {
          hasInstance: d('', NativeSymbol && NativeSymbol.hasInstance || SymbolPolyfill('hasInstance')),
          isConcatSpreadable: d('', NativeSymbol && NativeSymbol.isConcatSpreadable || SymbolPolyfill('isConcatSpreadable')),
          iterator: d('', NativeSymbol && NativeSymbol.iterator || SymbolPolyfill('iterator')),
          match: d('', NativeSymbol && NativeSymbol.match || SymbolPolyfill('match')),
          replace: d('', NativeSymbol && NativeSymbol.replace || SymbolPolyfill('replace')),
          search: d('', NativeSymbol && NativeSymbol.search || SymbolPolyfill('search')),
          species: d('', NativeSymbol && NativeSymbol.species || SymbolPolyfill('species')),
          split: d('', NativeSymbol && NativeSymbol.split || SymbolPolyfill('split')),
          toPrimitive: d('', NativeSymbol && NativeSymbol.toPrimitive || SymbolPolyfill('toPrimitive')),
          toStringTag: d('', NativeSymbol && NativeSymbol.toStringTag || SymbolPolyfill('toStringTag')),
          unscopables: d('', NativeSymbol && NativeSymbol.unscopables || SymbolPolyfill('unscopables'))
        });
      };
    }, {
      d: 157,
      'ext/global-this': 213
    } ],
    208: [ function(_dereq_, module, exports) {
      'use strict';
      var d = _dereq_('d'), validateSymbol = _dereq_('../../../validate-symbol');
      var registry = Object.create(null);
      module.exports = function(SymbolPolyfill) {
        return Object.defineProperties(SymbolPolyfill, {
          for: d(function(key) {
            if (registry[key]) {
              return registry[key];
            }
            return registry[key] = SymbolPolyfill(String(key));
          }),
          keyFor: d(function(symbol) {
            var key;
            validateSymbol(symbol);
            for (key in registry) {
              if (registry[key] === symbol) {
                return key;
              }
            }
            return undefined;
          })
        });
      };
    }, {
      '../../../validate-symbol': 210,
      d: 157
    } ],
    209: [ function(_dereq_, module, exports) {
      'use strict';
      var d = _dereq_('d'), validateSymbol = _dereq_('./validate-symbol'), NativeSymbol = _dereq_('ext/global-this').Symbol, generateName = _dereq_('./lib/private/generate-name'), setupStandardSymbols = _dereq_('./lib/private/setup/standard-symbols'), setupSymbolRegistry = _dereq_('./lib/private/setup/symbol-registry');
      var create = Object.create, defineProperties = Object.defineProperties, defineProperty = Object.defineProperty;
      var SymbolPolyfill, HiddenSymbol, isNativeSafe;
      if (typeof NativeSymbol === 'function') {
        try {
          String(NativeSymbol());
          isNativeSafe = true;
        } catch (ignore) {}
      } else {
        NativeSymbol = null;
      }
      HiddenSymbol = function Symbol(description) {
        if (this instanceof HiddenSymbol) {
          throw new TypeError('Symbol is not a constructor');
        }
        return SymbolPolyfill(description);
      };
      module.exports = SymbolPolyfill = function Symbol(description) {
        var symbol;
        if (this instanceof Symbol) {
          throw new TypeError('Symbol is not a constructor');
        }
        if (isNativeSafe) {
          return NativeSymbol(description);
        }
        symbol = create(HiddenSymbol.prototype);
        description = description === undefined ? '' : String(description);
        return defineProperties(symbol, {
          __description__: d('', description),
          __name__: d('', generateName(description))
        });
      };
      setupStandardSymbols(SymbolPolyfill);
      setupSymbolRegistry(SymbolPolyfill);
      defineProperties(HiddenSymbol.prototype, {
        constructor: d(SymbolPolyfill),
        toString: d('', function() {
          return this.__name__;
        })
      });
      defineProperties(SymbolPolyfill.prototype, {
        toString: d(function() {
          return 'Symbol (' + validateSymbol(this).__description__ + ')';
        }),
        valueOf: d(function() {
          return validateSymbol(this);
        })
      });
      defineProperty(SymbolPolyfill.prototype, SymbolPolyfill.toPrimitive, d('', function() {
        var symbol = validateSymbol(this);
        if (typeof symbol === 'symbol') {
          return symbol;
        }
        return symbol.toString();
      }));
      defineProperty(SymbolPolyfill.prototype, SymbolPolyfill.toStringTag, d('c', 'Symbol'));
      defineProperty(HiddenSymbol.prototype, SymbolPolyfill.toStringTag, d('c', SymbolPolyfill.prototype[SymbolPolyfill.toStringTag]));
      defineProperty(HiddenSymbol.prototype, SymbolPolyfill.toPrimitive, d('c', SymbolPolyfill.prototype[SymbolPolyfill.toPrimitive]));
    }, {
      './lib/private/generate-name': 206,
      './lib/private/setup/standard-symbols': 207,
      './lib/private/setup/symbol-registry': 208,
      './validate-symbol': 210,
      d: 157,
      'ext/global-this': 213
    } ],
    210: [ function(_dereq_, module, exports) {
      'use strict';
      var isSymbol = _dereq_('./is-symbol');
      module.exports = function(value) {
        if (!isSymbol(value)) {
          throw new TypeError(value + ' is not a symbol');
        }
        return value;
      };
    }, {
      './is-symbol': 205
    } ],
    211: [ function(_dereq_, module, exports) {
      'use strict';
      var d = _dereq_('d'), callable = _dereq_('es5-ext/object/valid-callable'), apply = Function.prototype.apply, call = Function.prototype.call, create = Object.create, defineProperty = Object.defineProperty, defineProperties = Object.defineProperties, hasOwnProperty = Object.prototype.hasOwnProperty, descriptor = {
        configurable: true,
        enumerable: false,
        writable: true
      }, on, once, off, emit, methods, descriptors, base;
      on = function(type, listener) {
        var data;
        callable(listener);
        if (!hasOwnProperty.call(this, '__ee__')) {
          data = descriptor.value = create(null);
          defineProperty(this, '__ee__', descriptor);
          descriptor.value = null;
        } else {
          data = this.__ee__;
        }
        if (!data[type]) {
          data[type] = listener;
        } else if (typeof data[type] === 'object') {
          data[type].push(listener);
        } else {
          data[type] = [ data[type], listener ];
        }
        return this;
      };
      once = function(type, listener) {
        var once, self;
        callable(listener);
        self = this;
        on.call(this, type, once = function() {
          off.call(self, type, once);
          apply.call(listener, this, arguments);
        });
        once.__eeOnceListener__ = listener;
        return this;
      };
      off = function(type, listener) {
        var data, listeners, candidate, i;
        callable(listener);
        if (!hasOwnProperty.call(this, '__ee__')) {
          return this;
        }
        data = this.__ee__;
        if (!data[type]) {
          return this;
        }
        listeners = data[type];
        if (typeof listeners === 'object') {
          for (i = 0; candidate = listeners[i]; ++i) {
            if (candidate === listener || candidate.__eeOnceListener__ === listener) {
              if (listeners.length === 2) {
                data[type] = listeners[i ? 0 : 1];
              } else {
                listeners.splice(i, 1);
              }
            }
          }
        } else {
          if (listeners === listener || listeners.__eeOnceListener__ === listener) {
            delete data[type];
          }
        }
        return this;
      };
      emit = function(type) {
        var i, l, listener, listeners, args;
        if (!hasOwnProperty.call(this, '__ee__')) {
          return;
        }
        listeners = this.__ee__[type];
        if (!listeners) {
          return;
        }
        if (typeof listeners === 'object') {
          l = arguments.length;
          args = new Array(l - 1);
          for (i = 1; i < l; ++i) {
            args[i - 1] = arguments[i];
          }
          listeners = listeners.slice();
          for (i = 0; listener = listeners[i]; ++i) {
            apply.call(listener, this, args);
          }
        } else {
          switch (arguments.length) {
           case 1:
            call.call(listeners, this);
            break;

           case 2:
            call.call(listeners, this, arguments[1]);
            break;

           case 3:
            call.call(listeners, this, arguments[1], arguments[2]);
            break;

           default:
            l = arguments.length;
            args = new Array(l - 1);
            for (i = 1; i < l; ++i) {
              args[i - 1] = arguments[i];
            }
            apply.call(listeners, this, args);
          }
        }
      };
      methods = {
        on: on,
        once: once,
        off: off,
        emit: emit
      };
      descriptors = {
        on: d(on),
        once: d(once),
        off: d(off),
        emit: d(emit)
      };
      base = defineProperties({}, descriptors);
      module.exports = exports = function(o) {
        return o == null ? create(base) : defineProperties(Object(o), descriptors);
      };
      exports.methods = methods;
    }, {
      d: 157,
      'es5-ext/object/valid-callable': 192
    } ],
    212: [ function(_dereq_, module, exports) {
      var naiveFallback = function() {
        if (typeof self === 'object' && self) {
          return self;
        }
        if (typeof window === 'object' && window) {
          return window;
        }
        throw new Error('Unable to resolve global `this`');
      };
      module.exports = function() {
        if (this) {
          return this;
        }
        try {
          Object.defineProperty(Object.prototype, '__global__', {
            get: function() {
              return this;
            },
            configurable: true
          });
        } catch (error) {
          return naiveFallback();
        }
        try {
          if (!__global__) {
            return naiveFallback();
          }
          return __global__;
        } finally {
          delete Object.prototype.__global__;
        }
      }();
    }, {} ],
    213: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = _dereq_('./is-implemented')() ? globalThis : _dereq_('./implementation');
    }, {
      './implementation': 212,
      './is-implemented': 214
    } ],
    214: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function() {
        if (typeof globalThis !== 'object') {
          return false;
        }
        if (!globalThis) {
          return false;
        }
        return globalThis.Array === Array;
      };
    }, {} ],
    215: [ function(_dereq_, module, exports) {
      module.exports = isPromise;
      function isPromise(obj) {
        return !!obj && (typeof obj === 'object' || typeof obj === 'function') && typeof obj.then === 'function';
      }
    }, {} ],
    216: [ function(_dereq_, module, exports) {
      'use strict';
      var toPosInt = _dereq_('es5-ext/number/to-pos-integer'), create = Object.create, hasOwnProperty = Object.prototype.hasOwnProperty;
      module.exports = function(limit) {
        var size = 0, base = 1, queue = create(null), map = create(null), index = 0, del;
        limit = toPosInt(limit);
        return {
          hit: function(id) {
            var oldIndex = map[id], nuIndex = ++index;
            queue[nuIndex] = id;
            map[id] = nuIndex;
            if (!oldIndex) {
              ++size;
              if (size <= limit) {
                return;
              }
              id = queue[base];
              del(id);
              return id;
            }
            delete queue[oldIndex];
            if (base !== oldIndex) {
              return;
            }
            while (!hasOwnProperty.call(queue, ++base)) {
              continue;
            }
          },
          delete: del = function(id) {
            var oldIndex = map[id];
            if (!oldIndex) {
              return;
            }
            delete queue[oldIndex];
            delete map[id];
            --size;
            if (base !== oldIndex) {
              return;
            }
            if (!size) {
              index = 0;
              base = 1;
              return;
            }
            while (!hasOwnProperty.call(queue, ++base)) {
              continue;
            }
          },
          clear: function() {
            size = 0;
            base = 1;
            queue = create(null);
            map = create(null);
            index = 0;
          }
        };
      };
    }, {
      'es5-ext/number/to-pos-integer': 176
    } ],
    217: [ function(_dereq_, module, exports) {
      'use strict';
      var aFrom = _dereq_('es5-ext/array/from'), objectMap = _dereq_('es5-ext/object/map'), mixin = _dereq_('es5-ext/object/mixin'), defineLength = _dereq_('es5-ext/function/_define-length'), nextTick = _dereq_('next-tick');
      var slice = Array.prototype.slice, apply = Function.prototype.apply, create = Object.create;
      _dereq_('../lib/registered-extensions').async = function(tbi, conf) {
        var waiting = create(null), cache = create(null), base = conf.memoized, original = conf.original, currentCallback, currentContext, currentArgs;
        conf.memoized = defineLength(function(arg) {
          var args = arguments, last = args[args.length - 1];
          if (typeof last === 'function') {
            currentCallback = last;
            args = slice.call(args, 0, -1);
          }
          return base.apply(currentContext = this, currentArgs = args);
        }, base);
        try {
          mixin(conf.memoized, base);
        } catch (ignore) {}
        conf.on('get', function(id) {
          var cb, context, args;
          if (!currentCallback) {
            return;
          }
          if (waiting[id]) {
            if (typeof waiting[id] === 'function') {
              waiting[id] = [ waiting[id], currentCallback ];
            } else {
              waiting[id].push(currentCallback);
            }
            currentCallback = null;
            return;
          }
          cb = currentCallback;
          context = currentContext;
          args = currentArgs;
          currentCallback = currentContext = currentArgs = null;
          nextTick(function() {
            var data;
            if (hasOwnProperty.call(cache, id)) {
              data = cache[id];
              conf.emit('getasync', id, args, context);
              apply.call(cb, data.context, data.args);
            } else {
              currentCallback = cb;
              currentContext = context;
              currentArgs = args;
              base.apply(context, args);
            }
          });
        });
        conf.original = function() {
          var args, cb, origCb, result;
          if (!currentCallback) {
            return apply.call(original, this, arguments);
          }
          args = aFrom(arguments);
          cb = function self(err) {
            var cb, args, id = self.id;
            if (id == null) {
              nextTick(apply.bind(self, this, arguments));
              return undefined;
            }
            delete self.id;
            cb = waiting[id];
            delete waiting[id];
            if (!cb) {
              return undefined;
            }
            args = aFrom(arguments);
            if (conf.has(id)) {
              if (err) {
                conf.delete(id);
              } else {
                cache[id] = {
                  context: this,
                  args: args
                };
                conf.emit('setasync', id, typeof cb === 'function' ? 1 : cb.length);
              }
            }
            if (typeof cb === 'function') {
              result = apply.call(cb, this, args);
            } else {
              cb.forEach(function(cb) {
                result = apply.call(cb, this, args);
              }, this);
            }
            return result;
          };
          origCb = currentCallback;
          currentCallback = currentContext = currentArgs = null;
          args.push(cb);
          result = apply.call(original, this, args);
          cb.cb = origCb;
          currentCallback = cb;
          return result;
        };
        conf.on('set', function(id) {
          if (!currentCallback) {
            conf.delete(id);
            return;
          }
          if (waiting[id]) {
            if (typeof waiting[id] === 'function') {
              waiting[id] = [ waiting[id], currentCallback.cb ];
            } else {
              waiting[id].push(currentCallback.cb);
            }
          } else {
            waiting[id] = currentCallback.cb;
          }
          delete currentCallback.cb;
          currentCallback.id = id;
          currentCallback = null;
        });
        conf.on('delete', function(id) {
          var result;
          if (hasOwnProperty.call(waiting, id)) {
            return;
          }
          if (!cache[id]) {
            return;
          }
          result = cache[id];
          delete cache[id];
          conf.emit('deleteasync', id, slice.call(result.args, 1));
        });
        conf.on('clear', function() {
          var oldCache = cache;
          cache = create(null);
          conf.emit('clearasync', objectMap(oldCache, function(data) {
            return slice.call(data.args, 1);
          }));
        });
      };
    }, {
      '../lib/registered-extensions': 225,
      'es5-ext/array/from': 160,
      'es5-ext/function/_define-length': 165,
      'es5-ext/object/map': 188,
      'es5-ext/object/mixin': 189,
      'next-tick': 235
    } ],
    218: [ function(_dereq_, module, exports) {
      'use strict';
      var callable = _dereq_('es5-ext/object/valid-callable'), forEach = _dereq_('es5-ext/object/for-each'), extensions = _dereq_('../lib/registered-extensions'), apply = Function.prototype.apply;
      extensions.dispose = function(dispose, conf, options) {
        var del;
        callable(dispose);
        if (options.async && extensions.async || options.promise && extensions.promise) {
          conf.on('deleteasync', del = function(id, resultArray) {
            apply.call(dispose, null, resultArray);
          });
          conf.on('clearasync', function(cache) {
            forEach(cache, function(result, id) {
              del(id, result);
            });
          });
          return;
        }
        conf.on('delete', del = function(id, result) {
          dispose(result);
        });
        conf.on('clear', function(cache) {
          forEach(cache, function(result, id) {
            del(id, result);
          });
        });
      };
    }, {
      '../lib/registered-extensions': 225,
      'es5-ext/object/for-each': 181,
      'es5-ext/object/valid-callable': 192
    } ],
    219: [ function(_dereq_, module, exports) {
      'use strict';
      var aFrom = _dereq_('es5-ext/array/from'), forEach = _dereq_('es5-ext/object/for-each'), nextTick = _dereq_('next-tick'), isPromise = _dereq_('is-promise'), timeout = _dereq_('timers-ext/valid-timeout'), extensions = _dereq_('../lib/registered-extensions');
      var noop = Function.prototype, max = Math.max, min = Math.min, create = Object.create;
      extensions.maxAge = function(maxAge, conf, options) {
        var timeouts, postfix, preFetchAge, preFetchTimeouts;
        maxAge = timeout(maxAge);
        if (!maxAge) {
          return;
        }
        timeouts = create(null);
        postfix = options.async && extensions.async || options.promise && extensions.promise ? 'async' : '';
        conf.on('set' + postfix, function(id) {
          timeouts[id] = setTimeout(function() {
            conf.delete(id);
          }, maxAge);
          if (typeof timeouts[id].unref === 'function') {
            timeouts[id].unref();
          }
          if (!preFetchTimeouts) {
            return;
          }
          if (preFetchTimeouts[id]) {
            if (preFetchTimeouts[id] !== 'nextTick') {
              clearTimeout(preFetchTimeouts[id]);
            }
          }
          preFetchTimeouts[id] = setTimeout(function() {
            delete preFetchTimeouts[id];
          }, preFetchAge);
          if (typeof preFetchTimeouts[id].unref === 'function') {
            preFetchTimeouts[id].unref();
          }
        });
        conf.on('delete' + postfix, function(id) {
          clearTimeout(timeouts[id]);
          delete timeouts[id];
          if (!preFetchTimeouts) {
            return;
          }
          if (preFetchTimeouts[id] !== 'nextTick') {
            clearTimeout(preFetchTimeouts[id]);
          }
          delete preFetchTimeouts[id];
        });
        if (options.preFetch) {
          if (options.preFetch === true || isNaN(options.preFetch)) {
            preFetchAge = .333;
          } else {
            preFetchAge = max(min(Number(options.preFetch), 1), 0);
          }
          if (preFetchAge) {
            preFetchTimeouts = {};
            preFetchAge = (1 - preFetchAge) * maxAge;
            conf.on('get' + postfix, function(id, args, context) {
              if (!preFetchTimeouts[id]) {
                preFetchTimeouts[id] = 'nextTick';
                nextTick(function() {
                  var result;
                  if (preFetchTimeouts[id] !== 'nextTick') {
                    return;
                  }
                  delete preFetchTimeouts[id];
                  conf.delete(id);
                  if (options.async) {
                    args = aFrom(args);
                    args.push(noop);
                  }
                  result = conf.memoized.apply(context, args);
                  if (options.promise) {
                    if (isPromise(result)) {
                      if (typeof result.done === 'function') {
                        result.done(noop, noop);
                      } else {
                        result.then(noop, noop);
                      }
                    }
                  }
                });
              }
            });
          }
        }
        conf.on('clear' + postfix, function() {
          forEach(timeouts, function(id) {
            clearTimeout(id);
          });
          timeouts = {};
          if (preFetchTimeouts) {
            forEach(preFetchTimeouts, function(id) {
              if (id !== 'nextTick') {
                clearTimeout(id);
              }
            });
            preFetchTimeouts = {};
          }
        });
      };
    }, {
      '../lib/registered-extensions': 225,
      'es5-ext/array/from': 160,
      'es5-ext/object/for-each': 181,
      'is-promise': 215,
      'next-tick': 235,
      'timers-ext/valid-timeout': 239
    } ],
    220: [ function(_dereq_, module, exports) {
      'use strict';
      var toPosInteger = _dereq_('es5-ext/number/to-pos-integer'), lruQueue = _dereq_('lru-queue'), extensions = _dereq_('../lib/registered-extensions');
      extensions.max = function(max, conf, options) {
        var postfix, queue, hit;
        max = toPosInteger(max);
        if (!max) {
          return;
        }
        queue = lruQueue(max);
        postfix = options.async && extensions.async || options.promise && extensions.promise ? 'async' : '';
        conf.on('set' + postfix, hit = function(id) {
          id = queue.hit(id);
          if (id === undefined) {
            return;
          }
          conf.delete(id);
        });
        conf.on('get' + postfix, hit);
        conf.on('delete' + postfix, queue.delete);
        conf.on('clear' + postfix, queue.clear);
      };
    }, {
      '../lib/registered-extensions': 225,
      'es5-ext/number/to-pos-integer': 176,
      'lru-queue': 216
    } ],
    221: [ function(_dereq_, module, exports) {
      'use strict';
      var objectMap = _dereq_('es5-ext/object/map'), primitiveSet = _dereq_('es5-ext/object/primitive-set'), ensureString = _dereq_('es5-ext/object/validate-stringifiable-value'), toShortString = _dereq_('es5-ext/to-short-string-representation'), isPromise = _dereq_('is-promise'), nextTick = _dereq_('next-tick');
      var create = Object.create, supportedModes = primitiveSet('then', 'then:finally', 'done', 'done:finally');
      _dereq_('../lib/registered-extensions').promise = function(mode, conf) {
        var waiting = create(null), cache = create(null), promises = create(null);
        if (mode === true) {
          mode = null;
        } else {
          mode = ensureString(mode);
          if (!supportedModes[mode]) {
            throw new TypeError('\'' + toShortString(mode) + '\' is not valid promise mode');
          }
        }
        conf.on('set', function(id, ignore, promise) {
          var isFailed = false;
          if (!isPromise(promise)) {
            cache[id] = promise;
            conf.emit('setasync', id, 1);
            return;
          }
          waiting[id] = 1;
          promises[id] = promise;
          var onSuccess = function(result) {
            var count = waiting[id];
            if (isFailed) {
              throw new Error('Memoizee error: Detected unordered then|done & finally resolution, which ' + 'in turn makes proper detection of success/failure impossible (when in ' + '\'done:finally\' mode)\n' + 'Consider to rely on \'then\' or \'done\' mode instead.');
            }
            if (!count) {
              return;
            }
            delete waiting[id];
            cache[id] = result;
            conf.emit('setasync', id, count);
          };
          var onFailure = function() {
            isFailed = true;
            if (!waiting[id]) {
              return;
            }
            delete waiting[id];
            delete promises[id];
            conf.delete(id);
          };
          var resolvedMode = mode;
          if (!resolvedMode) {
            resolvedMode = 'then';
          }
          if (resolvedMode === 'then') {
            var nextTickFailure = function() {
              nextTick(onFailure);
            };
            promise = promise.then(function(result) {
              nextTick(onSuccess.bind(this, result));
            }, nextTickFailure);
            if (typeof promise.finally === 'function') {
              promise.finally(nextTickFailure);
            }
          } else if (resolvedMode === 'done') {
            if (typeof promise.done !== 'function') {
              throw new Error('Memoizee error: Retrieved promise does not implement \'done\' ' + 'in \'done\' mode');
            }
            promise.done(onSuccess, onFailure);
          } else if (resolvedMode === 'done:finally') {
            if (typeof promise.done !== 'function') {
              throw new Error('Memoizee error: Retrieved promise does not implement \'done\' ' + 'in \'done:finally\' mode');
            }
            if (typeof promise.finally !== 'function') {
              throw new Error('Memoizee error: Retrieved promise does not implement \'finally\' ' + 'in \'done:finally\' mode');
            }
            promise.done(onSuccess);
            promise.finally(onFailure);
          }
        });
        conf.on('get', function(id, args, context) {
          var promise;
          if (waiting[id]) {
            ++waiting[id];
            return;
          }
          promise = promises[id];
          var emit = function() {
            conf.emit('getasync', id, args, context);
          };
          if (isPromise(promise)) {
            if (typeof promise.done === 'function') {
              promise.done(emit);
            } else {
              promise.then(function() {
                nextTick(emit);
              });
            }
          } else {
            emit();
          }
        });
        conf.on('delete', function(id) {
          delete promises[id];
          if (waiting[id]) {
            delete waiting[id];
            return;
          }
          if (!hasOwnProperty.call(cache, id)) {
            return;
          }
          var result = cache[id];
          delete cache[id];
          conf.emit('deleteasync', id, [ result ]);
        });
        conf.on('clear', function() {
          var oldCache = cache;
          cache = create(null);
          waiting = create(null);
          promises = create(null);
          conf.emit('clearasync', objectMap(oldCache, function(data) {
            return [ data ];
          }));
        });
      };
    }, {
      '../lib/registered-extensions': 225,
      'es5-ext/object/map': 188,
      'es5-ext/object/primitive-set': 191,
      'es5-ext/object/validate-stringifiable-value': 194,
      'es5-ext/to-short-string-representation': 201,
      'is-promise': 215,
      'next-tick': 235
    } ],
    222: [ function(_dereq_, module, exports) {
      'use strict';
      var d = _dereq_('d'), extensions = _dereq_('../lib/registered-extensions'), create = Object.create, defineProperties = Object.defineProperties;
      extensions.refCounter = function(ignore, conf, options) {
        var cache, postfix;
        cache = create(null);
        postfix = options.async && extensions.async || options.promise && extensions.promise ? 'async' : '';
        conf.on('set' + postfix, function(id, length) {
          cache[id] = length || 1;
        });
        conf.on('get' + postfix, function(id) {
          ++cache[id];
        });
        conf.on('delete' + postfix, function(id) {
          delete cache[id];
        });
        conf.on('clear' + postfix, function() {
          cache = {};
        });
        defineProperties(conf.memoized, {
          deleteRef: d(function() {
            var id = conf.get(arguments);
            if (id === null) {
              return null;
            }
            if (!cache[id]) {
              return null;
            }
            if (!--cache[id]) {
              conf.delete(id);
              return true;
            }
            return false;
          }),
          getRefCount: d(function() {
            var id = conf.get(arguments);
            if (id === null) {
              return 0;
            }
            if (!cache[id]) {
              return 0;
            }
            return cache[id];
          })
        });
      };
    }, {
      '../lib/registered-extensions': 225,
      d: 157
    } ],
    223: [ function(_dereq_, module, exports) {
      'use strict';
      var normalizeOpts = _dereq_('es5-ext/object/normalize-options'), resolveLength = _dereq_('./lib/resolve-length'), plain = _dereq_('./plain');
      module.exports = function(fn) {
        var options = normalizeOpts(arguments[1]), length;
        if (!options.normalizer) {
          length = options.length = resolveLength(options.length, fn.length, options.async);
          if (length !== 0) {
            if (options.primitive) {
              if (length === false) {
                options.normalizer = _dereq_('./normalizers/primitive');
              } else if (length > 1) {
                options.normalizer = _dereq_('./normalizers/get-primitive-fixed')(length);
              }
            } else if (length === false) {
              options.normalizer = _dereq_('./normalizers/get')();
            } else if (length === 1) {
              options.normalizer = _dereq_('./normalizers/get-1')();
            } else {
              options.normalizer = _dereq_('./normalizers/get-fixed')(length);
            }
          }
        }
        if (options.async) {
          _dereq_('./ext/async');
        }
        if (options.promise) {
          _dereq_('./ext/promise');
        }
        if (options.dispose) {
          _dereq_('./ext/dispose');
        }
        if (options.maxAge) {
          _dereq_('./ext/max-age');
        }
        if (options.max) {
          _dereq_('./ext/max');
        }
        if (options.refCounter) {
          _dereq_('./ext/ref-counter');
        }
        return plain(fn, options);
      };
    }, {
      './ext/async': 217,
      './ext/dispose': 218,
      './ext/max': 220,
      './ext/max-age': 219,
      './ext/promise': 221,
      './ext/ref-counter': 222,
      './lib/resolve-length': 226,
      './normalizers/get': 232,
      './normalizers/get-1': 229,
      './normalizers/get-fixed': 230,
      './normalizers/get-primitive-fixed': 231,
      './normalizers/primitive': 233,
      './plain': 234,
      'es5-ext/object/normalize-options': 190
    } ],
    224: [ function(_dereq_, module, exports) {
      'use strict';
      var customError = _dereq_('es5-ext/error/custom'), defineLength = _dereq_('es5-ext/function/_define-length'), d = _dereq_('d'), ee = _dereq_('event-emitter').methods, resolveResolve = _dereq_('./resolve-resolve'), resolveNormalize = _dereq_('./resolve-normalize');
      var apply = Function.prototype.apply, call = Function.prototype.call, create = Object.create, defineProperties = Object.defineProperties, on = ee.on, emit = ee.emit;
      module.exports = function(original, length, options) {
        var cache = create(null), conf, memLength, get, set, del, clear, extDel, extGet, extHas, normalizer, getListeners, setListeners, deleteListeners, memoized, resolve;
        if (length !== false) {
          memLength = length;
        } else if (isNaN(original.length)) {
          memLength = 1;
        } else {
          memLength = original.length;
        }
        if (options.normalizer) {
          normalizer = resolveNormalize(options.normalizer);
          get = normalizer.get;
          set = normalizer.set;
          del = normalizer.delete;
          clear = normalizer.clear;
        }
        if (options.resolvers != null) {
          resolve = resolveResolve(options.resolvers);
        }
        if (get) {
          memoized = defineLength(function(arg) {
            var id, result, args = arguments;
            if (resolve) {
              args = resolve(args);
            }
            id = get(args);
            if (id !== null) {
              if (hasOwnProperty.call(cache, id)) {
                if (getListeners) {
                  conf.emit('get', id, args, this);
                }
                return cache[id];
              }
            }
            if (args.length === 1) {
              result = call.call(original, this, args[0]);
            } else {
              result = apply.call(original, this, args);
            }
            if (id === null) {
              id = get(args);
              if (id !== null) {
                throw customError('Circular invocation', 'CIRCULAR_INVOCATION');
              }
              id = set(args);
            } else if (hasOwnProperty.call(cache, id)) {
              throw customError('Circular invocation', 'CIRCULAR_INVOCATION');
            }
            cache[id] = result;
            if (setListeners) {
              conf.emit('set', id, null, result);
            }
            return result;
          }, memLength);
        } else if (length === 0) {
          memoized = function() {
            var result;
            if (hasOwnProperty.call(cache, 'data')) {
              if (getListeners) {
                conf.emit('get', 'data', arguments, this);
              }
              return cache.data;
            }
            if (arguments.length) {
              result = apply.call(original, this, arguments);
            } else {
              result = call.call(original, this);
            }
            if (hasOwnProperty.call(cache, 'data')) {
              throw customError('Circular invocation', 'CIRCULAR_INVOCATION');
            }
            cache.data = result;
            if (setListeners) {
              conf.emit('set', 'data', null, result);
            }
            return result;
          };
        } else {
          memoized = function(arg) {
            var result, args = arguments, id;
            if (resolve) {
              args = resolve(arguments);
            }
            id = String(args[0]);
            if (hasOwnProperty.call(cache, id)) {
              if (getListeners) {
                conf.emit('get', id, args, this);
              }
              return cache[id];
            }
            if (args.length === 1) {
              result = call.call(original, this, args[0]);
            } else {
              result = apply.call(original, this, args);
            }
            if (hasOwnProperty.call(cache, id)) {
              throw customError('Circular invocation', 'CIRCULAR_INVOCATION');
            }
            cache[id] = result;
            if (setListeners) {
              conf.emit('set', id, null, result);
            }
            return result;
          };
        }
        conf = {
          original: original,
          memoized: memoized,
          profileName: options.profileName,
          get: function(args) {
            if (resolve) {
              args = resolve(args);
            }
            if (get) {
              return get(args);
            }
            return String(args[0]);
          },
          has: function(id) {
            return hasOwnProperty.call(cache, id);
          },
          delete: function(id) {
            var result;
            if (!hasOwnProperty.call(cache, id)) {
              return;
            }
            if (del) {
              del(id);
            }
            result = cache[id];
            delete cache[id];
            if (deleteListeners) {
              conf.emit('delete', id, result);
            }
          },
          clear: function() {
            var oldCache = cache;
            if (clear) {
              clear();
            }
            cache = create(null);
            conf.emit('clear', oldCache);
          },
          on: function(type, listener) {
            if (type === 'get') {
              getListeners = true;
            } else if (type === 'set') {
              setListeners = true;
            } else if (type === 'delete') {
              deleteListeners = true;
            }
            return on.call(this, type, listener);
          },
          emit: emit,
          updateEnv: function() {
            original = conf.original;
          }
        };
        if (get) {
          extDel = defineLength(function(arg) {
            var id, args = arguments;
            if (resolve) {
              args = resolve(args);
            }
            id = get(args);
            if (id === null) {
              return;
            }
            conf.delete(id);
          }, memLength);
        } else if (length === 0) {
          extDel = function() {
            return conf.delete('data');
          };
        } else {
          extDel = function(arg) {
            if (resolve) {
              arg = resolve(arguments)[0];
            }
            return conf.delete(arg);
          };
        }
        extGet = defineLength(function() {
          var id, args = arguments;
          if (length === 0) {
            return cache.data;
          }
          if (resolve) {
            args = resolve(args);
          }
          if (get) {
            id = get(args);
          } else {
            id = String(args[0]);
          }
          return cache[id];
        });
        extHas = defineLength(function() {
          var id, args = arguments;
          if (length === 0) {
            return conf.has('data');
          }
          if (resolve) {
            args = resolve(args);
          }
          if (get) {
            id = get(args);
          } else {
            id = String(args[0]);
          }
          if (id === null) {
            return false;
          }
          return conf.has(id);
        });
        defineProperties(memoized, {
          __memoized__: d(true),
          delete: d(extDel),
          clear: d(conf.clear),
          _get: d(extGet),
          _has: d(extHas)
        });
        return conf;
      };
    }, {
      './resolve-normalize': 227,
      './resolve-resolve': 228,
      d: 157,
      'es5-ext/error/custom': 164,
      'es5-ext/function/_define-length': 165,
      'event-emitter': 211
    } ],
    225: [ function(_dereq_, module, exports) {
      'use strict';
    }, {} ],
    226: [ function(_dereq_, module, exports) {
      'use strict';
      var toPosInt = _dereq_('es5-ext/number/to-pos-integer');
      module.exports = function(optsLength, fnLength, isAsync) {
        var length;
        if (isNaN(optsLength)) {
          length = fnLength;
          if (!(length >= 0)) {
            return 1;
          }
          if (isAsync && length) {
            return length - 1;
          }
          return length;
        }
        if (optsLength === false) {
          return false;
        }
        return toPosInt(optsLength);
      };
    }, {
      'es5-ext/number/to-pos-integer': 176
    } ],
    227: [ function(_dereq_, module, exports) {
      'use strict';
      var callable = _dereq_('es5-ext/object/valid-callable');
      module.exports = function(userNormalizer) {
        var normalizer;
        if (typeof userNormalizer === 'function') {
          return {
            set: userNormalizer,
            get: userNormalizer
          };
        }
        normalizer = {
          get: callable(userNormalizer.get)
        };
        if (userNormalizer.set !== undefined) {
          normalizer.set = callable(userNormalizer.set);
          if (userNormalizer.delete) {
            normalizer.delete = callable(userNormalizer.delete);
          }
          if (userNormalizer.clear) {
            normalizer.clear = callable(userNormalizer.clear);
          }
          return normalizer;
        }
        normalizer.set = normalizer.get;
        return normalizer;
      };
    }, {
      'es5-ext/object/valid-callable': 192
    } ],
    228: [ function(_dereq_, module, exports) {
      'use strict';
      var toArray = _dereq_('es5-ext/array/to-array'), isValue = _dereq_('es5-ext/object/is-value'), callable = _dereq_('es5-ext/object/valid-callable');
      var slice = Array.prototype.slice, resolveArgs;
      resolveArgs = function(args) {
        return this.map(function(resolve, i) {
          return resolve ? resolve(args[i]) : args[i];
        }).concat(slice.call(args, this.length));
      };
      module.exports = function(resolvers) {
        resolvers = toArray(resolvers);
        resolvers.forEach(function(resolve) {
          if (isValue(resolve)) {
            callable(resolve);
          }
        });
        return resolveArgs.bind(resolvers);
      };
    }, {
      'es5-ext/array/to-array': 163,
      'es5-ext/object/is-value': 184,
      'es5-ext/object/valid-callable': 192
    } ],
    229: [ function(_dereq_, module, exports) {
      'use strict';
      var indexOf = _dereq_('es5-ext/array/#/e-index-of');
      module.exports = function() {
        var lastId = 0, argsMap = [], cache = [];
        return {
          get: function(args) {
            var index = indexOf.call(argsMap, args[0]);
            return index === -1 ? null : cache[index];
          },
          set: function(args) {
            argsMap.push(args[0]);
            cache.push(++lastId);
            return lastId;
          },
          delete: function(id) {
            var index = indexOf.call(cache, id);
            if (index !== -1) {
              argsMap.splice(index, 1);
              cache.splice(index, 1);
            }
          },
          clear: function() {
            argsMap = [];
            cache = [];
          }
        };
      };
    }, {
      'es5-ext/array/#/e-index-of': 159
    } ],
    230: [ function(_dereq_, module, exports) {
      'use strict';
      var indexOf = _dereq_('es5-ext/array/#/e-index-of'), create = Object.create;
      module.exports = function(length) {
        var lastId = 0, map = [ [], [] ], cache = create(null);
        return {
          get: function(args) {
            var index = 0, set = map, i;
            while (index < length - 1) {
              i = indexOf.call(set[0], args[index]);
              if (i === -1) {
                return null;
              }
              set = set[1][i];
              ++index;
            }
            i = indexOf.call(set[0], args[index]);
            if (i === -1) {
              return null;
            }
            return set[1][i] || null;
          },
          set: function(args) {
            var index = 0, set = map, i;
            while (index < length - 1) {
              i = indexOf.call(set[0], args[index]);
              if (i === -1) {
                i = set[0].push(args[index]) - 1;
                set[1].push([ [], [] ]);
              }
              set = set[1][i];
              ++index;
            }
            i = indexOf.call(set[0], args[index]);
            if (i === -1) {
              i = set[0].push(args[index]) - 1;
            }
            set[1][i] = ++lastId;
            cache[lastId] = args;
            return lastId;
          },
          delete: function(id) {
            var index = 0, set = map, i, path = [], args = cache[id];
            while (index < length - 1) {
              i = indexOf.call(set[0], args[index]);
              if (i === -1) {
                return;
              }
              path.push(set, i);
              set = set[1][i];
              ++index;
            }
            i = indexOf.call(set[0], args[index]);
            if (i === -1) {
              return;
            }
            id = set[1][i];
            set[0].splice(i, 1);
            set[1].splice(i, 1);
            while (!set[0].length && path.length) {
              i = path.pop();
              set = path.pop();
              set[0].splice(i, 1);
              set[1].splice(i, 1);
            }
            delete cache[id];
          },
          clear: function() {
            map = [ [], [] ];
            cache = create(null);
          }
        };
      };
    }, {
      'es5-ext/array/#/e-index-of': 159
    } ],
    231: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function(length) {
        if (!length) {
          return function() {
            return '';
          };
        }
        return function(args) {
          var id = String(args[0]), i = 0, currentLength = length;
          while (--currentLength) {
            id += '\x01' + args[++i];
          }
          return id;
        };
      };
    }, {} ],
    232: [ function(_dereq_, module, exports) {
      'use strict';
      var indexOf = _dereq_('es5-ext/array/#/e-index-of');
      var create = Object.create;
      module.exports = function() {
        var lastId = 0, map = [], cache = create(null);
        return {
          get: function(args) {
            var index = 0, set = map, i, length = args.length;
            if (length === 0) {
              return set[length] || null;
            }
            if (set = set[length]) {
              while (index < length - 1) {
                i = indexOf.call(set[0], args[index]);
                if (i === -1) {
                  return null;
                }
                set = set[1][i];
                ++index;
              }
              i = indexOf.call(set[0], args[index]);
              if (i === -1) {
                return null;
              }
              return set[1][i] || null;
            }
            return null;
          },
          set: function(args) {
            var index = 0, set = map, i, length = args.length;
            if (length === 0) {
              set[length] = ++lastId;
            } else {
              if (!set[length]) {
                set[length] = [ [], [] ];
              }
              set = set[length];
              while (index < length - 1) {
                i = indexOf.call(set[0], args[index]);
                if (i === -1) {
                  i = set[0].push(args[index]) - 1;
                  set[1].push([ [], [] ]);
                }
                set = set[1][i];
                ++index;
              }
              i = indexOf.call(set[0], args[index]);
              if (i === -1) {
                i = set[0].push(args[index]) - 1;
              }
              set[1][i] = ++lastId;
            }
            cache[lastId] = args;
            return lastId;
          },
          delete: function(id) {
            var index = 0, set = map, i, args = cache[id], length = args.length, path = [];
            if (length === 0) {
              delete set[length];
            } else if (set = set[length]) {
              while (index < length - 1) {
                i = indexOf.call(set[0], args[index]);
                if (i === -1) {
                  return;
                }
                path.push(set, i);
                set = set[1][i];
                ++index;
              }
              i = indexOf.call(set[0], args[index]);
              if (i === -1) {
                return;
              }
              id = set[1][i];
              set[0].splice(i, 1);
              set[1].splice(i, 1);
              while (!set[0].length && path.length) {
                i = path.pop();
                set = path.pop();
                set[0].splice(i, 1);
                set[1].splice(i, 1);
              }
            }
            delete cache[id];
          },
          clear: function() {
            map = [];
            cache = create(null);
          }
        };
      };
    }, {
      'es5-ext/array/#/e-index-of': 159
    } ],
    233: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = function(args) {
        var id, i, length = args.length;
        if (!length) {
          return '\x02';
        }
        id = String(args[i = 0]);
        while (--length) {
          id += '\x01' + args[++i];
        }
        return id;
      };
    }, {} ],
    234: [ function(_dereq_, module, exports) {
      'use strict';
      var callable = _dereq_('es5-ext/object/valid-callable'), forEach = _dereq_('es5-ext/object/for-each'), extensions = _dereq_('./lib/registered-extensions'), configure = _dereq_('./lib/configure-map'), resolveLength = _dereq_('./lib/resolve-length');
      module.exports = function self(fn) {
        var options, length, conf;
        callable(fn);
        options = Object(arguments[1]);
        if (options.async && options.promise) {
          throw new Error('Options \'async\' and \'promise\' cannot be used together');
        }
        if (hasOwnProperty.call(fn, '__memoized__') && !options.force) {
          return fn;
        }
        length = resolveLength(options.length, fn.length, options.async && extensions.async);
        conf = configure(fn, length, options);
        forEach(extensions, function(extFn, name) {
          if (options[name]) {
            extFn(options[name], conf, options);
          }
        });
        if (self.__profiler__) {
          self.__profiler__(conf);
        }
        conf.updateEnv();
        return conf.memoized;
      };
    }, {
      './lib/configure-map': 224,
      './lib/registered-extensions': 225,
      './lib/resolve-length': 226,
      'es5-ext/object/for-each': 181,
      'es5-ext/object/valid-callable': 192
    } ],
    235: [ function(_dereq_, module, exports) {
      (function(process, setImmediate) {
        'use strict';
        var callable, byObserver;
        callable = function(fn) {
          if (typeof fn !== 'function') {
            throw new TypeError(fn + ' is not a function');
          }
          return fn;
        };
        byObserver = function(Observer) {
          var node = document.createTextNode(''), queue, currentQueue, i = 0;
          new Observer(function() {
            var callback;
            if (!queue) {
              if (!currentQueue) {
                return;
              }
              queue = currentQueue;
            } else if (currentQueue) {
              queue = currentQueue.concat(queue);
            }
            currentQueue = queue;
            queue = null;
            if (typeof currentQueue === 'function') {
              callback = currentQueue;
              currentQueue = null;
              callback();
              return;
            }
            node.data = i = ++i % 2;
            while (currentQueue) {
              callback = currentQueue.shift();
              if (!currentQueue.length) {
                currentQueue = null;
              }
              callback();
            }
          }).observe(node, {
            characterData: true
          });
          return function(fn) {
            callable(fn);
            if (queue) {
              if (typeof queue === 'function') {
                queue = [ queue, fn ];
              } else {
                queue.push(fn);
              }
              return;
            }
            queue = fn;
            node.data = i = ++i % 2;
          };
        };
        module.exports = function() {
          if (typeof process === 'object' && process && typeof process.nextTick === 'function') {
            return process.nextTick;
          }
          if (typeof document === 'object' && document) {
            if (typeof MutationObserver === 'function') {
              return byObserver(MutationObserver);
            }
            if (typeof WebKitMutationObserver === 'function') {
              return byObserver(WebKitMutationObserver);
            }
          }
          if (typeof setImmediate === 'function') {
            return function(cb) {
              setImmediate(callable(cb));
            };
          }
          if (typeof setTimeout === 'function' || typeof setTimeout === 'object') {
            return function(cb) {
              setTimeout(callable(cb), 0);
            };
          }
          return null;
        }();
      }).call(this, _dereq_('_process'), _dereq_('timers').setImmediate);
    }, {
      _process: 236,
      timers: 237
    } ],
    236: [ function(_dereq_, module, exports) {
      var process = module.exports = {};
      var cachedSetTimeout;
      var cachedClearTimeout;
      function defaultSetTimout() {
        throw new Error('setTimeout has not been defined');
      }
      function defaultClearTimeout() {
        throw new Error('clearTimeout has not been defined');
      }
      (function() {
        try {
          if (typeof setTimeout === 'function') {
            cachedSetTimeout = setTimeout;
          } else {
            cachedSetTimeout = defaultSetTimout;
          }
        } catch (e) {
          cachedSetTimeout = defaultSetTimout;
        }
        try {
          if (typeof clearTimeout === 'function') {
            cachedClearTimeout = clearTimeout;
          } else {
            cachedClearTimeout = defaultClearTimeout;
          }
        } catch (e) {
          cachedClearTimeout = defaultClearTimeout;
        }
      })();
      function runTimeout(fun) {
        if (cachedSetTimeout === setTimeout) {
          return setTimeout(fun, 0);
        }
        if ((cachedSetTimeout === defaultSetTimout || !cachedSetTimeout) && setTimeout) {
          cachedSetTimeout = setTimeout;
          return setTimeout(fun, 0);
        }
        try {
          return cachedSetTimeout(fun, 0);
        } catch (e) {
          try {
            return cachedSetTimeout.call(null, fun, 0);
          } catch (e) {
            return cachedSetTimeout.call(this, fun, 0);
          }
        }
      }
      function runClearTimeout(marker) {
        if (cachedClearTimeout === clearTimeout) {
          return clearTimeout(marker);
        }
        if ((cachedClearTimeout === defaultClearTimeout || !cachedClearTimeout) && clearTimeout) {
          cachedClearTimeout = clearTimeout;
          return clearTimeout(marker);
        }
        try {
          return cachedClearTimeout(marker);
        } catch (e) {
          try {
            return cachedClearTimeout.call(null, marker);
          } catch (e) {
            return cachedClearTimeout.call(this, marker);
          }
        }
      }
      var queue = [];
      var draining = false;
      var currentQueue;
      var queueIndex = -1;
      function cleanUpNextTick() {
        if (!draining || !currentQueue) {
          return;
        }
        draining = false;
        if (currentQueue.length) {
          queue = currentQueue.concat(queue);
        } else {
          queueIndex = -1;
        }
        if (queue.length) {
          drainQueue();
        }
      }
      function drainQueue() {
        if (draining) {
          return;
        }
        var timeout = runTimeout(cleanUpNextTick);
        draining = true;
        var len = queue.length;
        while (len) {
          currentQueue = queue;
          queue = [];
          while (++queueIndex < len) {
            if (currentQueue) {
              currentQueue[queueIndex].run();
            }
          }
          queueIndex = -1;
          len = queue.length;
        }
        currentQueue = null;
        draining = false;
        runClearTimeout(timeout);
      }
      process.nextTick = function(fun) {
        var args = new Array(arguments.length - 1);
        if (arguments.length > 1) {
          for (var i = 1; i < arguments.length; i++) {
            args[i - 1] = arguments[i];
          }
        }
        queue.push(new Item(fun, args));
        if (queue.length === 1 && !draining) {
          runTimeout(drainQueue);
        }
      };
      function Item(fun, array) {
        this.fun = fun;
        this.array = array;
      }
      Item.prototype.run = function() {
        this.fun.apply(null, this.array);
      };
      process.title = 'browser';
      process.browser = true;
      process.env = {};
      process.argv = [];
      process.version = '';
      process.versions = {};
      function noop() {}
      process.on = noop;
      process.addListener = noop;
      process.once = noop;
      process.off = noop;
      process.removeListener = noop;
      process.removeAllListeners = noop;
      process.emit = noop;
      process.prependListener = noop;
      process.prependOnceListener = noop;
      process.listeners = function(name) {
        return [];
      };
      process.binding = function(name) {
        throw new Error('process.binding is not supported');
      };
      process.cwd = function() {
        return '/';
      };
      process.chdir = function(dir) {
        throw new Error('process.chdir is not supported');
      };
      process.umask = function() {
        return 0;
      };
    }, {} ],
    237: [ function(_dereq_, module, exports) {
      (function(setImmediate, clearImmediate) {
        var nextTick = _dereq_('process/browser.js').nextTick;
        var apply = Function.prototype.apply;
        var slice = Array.prototype.slice;
        var immediateIds = {};
        var nextImmediateId = 0;
        exports.setTimeout = function() {
          return new Timeout(apply.call(setTimeout, window, arguments), clearTimeout);
        };
        exports.setInterval = function() {
          return new Timeout(apply.call(setInterval, window, arguments), clearInterval);
        };
        exports.clearTimeout = exports.clearInterval = function(timeout) {
          timeout.close();
        };
        function Timeout(id, clearFn) {
          this._id = id;
          this._clearFn = clearFn;
        }
        Timeout.prototype.unref = Timeout.prototype.ref = function() {};
        Timeout.prototype.close = function() {
          this._clearFn.call(window, this._id);
        };
        exports.enroll = function(item, msecs) {
          clearTimeout(item._idleTimeoutId);
          item._idleTimeout = msecs;
        };
        exports.unenroll = function(item) {
          clearTimeout(item._idleTimeoutId);
          item._idleTimeout = -1;
        };
        exports._unrefActive = exports.active = function(item) {
          clearTimeout(item._idleTimeoutId);
          var msecs = item._idleTimeout;
          if (msecs >= 0) {
            item._idleTimeoutId = setTimeout(function onTimeout() {
              if (item._onTimeout) {
                item._onTimeout();
              }
            }, msecs);
          }
        };
        exports.setImmediate = typeof setImmediate === 'function' ? setImmediate : function(fn) {
          var id = nextImmediateId++;
          var args = arguments.length < 2 ? false : slice.call(arguments, 1);
          immediateIds[id] = true;
          nextTick(function onNextTick() {
            if (immediateIds[id]) {
              if (args) {
                fn.apply(null, args);
              } else {
                fn.call(null);
              }
              exports.clearImmediate(id);
            }
          });
          return id;
        };
        exports.clearImmediate = typeof clearImmediate === 'function' ? clearImmediate : function(id) {
          delete immediateIds[id];
        };
      }).call(this, _dereq_('timers').setImmediate, _dereq_('timers').clearImmediate);
    }, {
      'process/browser.js': 236,
      timers: 237
    } ],
    238: [ function(_dereq_, module, exports) {
      'use strict';
      module.exports = 2147483647;
    }, {} ],
    239: [ function(_dereq_, module, exports) {
      'use strict';
      var toPosInt = _dereq_('es5-ext/number/to-pos-integer'), maxTimeout = _dereq_('./max-timeout');
      module.exports = function(value) {
        value = toPosInt(value);
        if (value > maxTimeout) {
          throw new TypeError(value + ' exceeds maximum possible timeout');
        }
        return value;
      };
    }, {
      './max-timeout': 238,
      'es5-ext/number/to-pos-integer': 176
    } ],
    240: [ function(_dereq_, module, exports) {
      'use strict';
      var isPrototype = _dereq_('../prototype/is');
      module.exports = function(value) {
        if (typeof value !== 'function') {
          return false;
        }
        if (!hasOwnProperty.call(value, 'length')) {
          return false;
        }
        try {
          if (typeof value.length !== 'number') {
            return false;
          }
          if (typeof value.call !== 'function') {
            return false;
          }
          if (typeof value.apply !== 'function') {
            return false;
          }
        } catch (error) {
          return false;
        }
        return !isPrototype(value);
      };
    }, {
      '../prototype/is': 243
    } ],
    241: [ function(_dereq_, module, exports) {
      'use strict';
      var isValue = _dereq_('../value/is');
      var possibleTypes = {
        object: true,
        function: true,
        undefined: true
      };
      module.exports = function(value) {
        if (!isValue(value)) {
          return false;
        }
        return hasOwnProperty.call(possibleTypes, typeof value);
      };
    }, {
      '../value/is': 244
    } ],
    242: [ function(_dereq_, module, exports) {
      'use strict';
      var isFunction = _dereq_('../function/is');
      var classRe = /^\s*class[\s{/}]/, functionToString = Function.prototype.toString;
      module.exports = function(value) {
        if (!isFunction(value)) {
          return false;
        }
        if (classRe.test(functionToString.call(value))) {
          return false;
        }
        return true;
      };
    }, {
      '../function/is': 240
    } ],
    243: [ function(_dereq_, module, exports) {
      'use strict';
      var isObject = _dereq_('../object/is');
      module.exports = function(value) {
        if (!isObject(value)) {
          return false;
        }
        try {
          if (!value.constructor) {
            return false;
          }
          return value.constructor.prototype === value;
        } catch (error) {
          return false;
        }
      };
    }, {
      '../object/is': 241
    } ],
    244: [ function(_dereq_, module, exports) {
      'use strict';
      var _undefined = void 0;
      module.exports = function(value) {
        return value !== _undefined && value !== null;
      };
    }, {} ],
    245: [ function(_dereq_, module, exports) {
      (function(global) {
        (function(self) {
          'use strict';
          if (self.WeakMap) {
            return;
          }
          var hasOwnProperty = Object.prototype.hasOwnProperty;
          var defineProperty = function(object, name, value) {
            if (Object.defineProperty) {
              Object.defineProperty(object, name, {
                configurable: true,
                writable: true,
                value: value
              });
            } else {
              object[name] = value;
            }
          };
          self.WeakMap = function() {
            function WeakMap() {
              if (this === void 0) {
                throw new TypeError('Constructor WeakMap requires \'new\'');
              }
              defineProperty(this, '_id', genId('_WeakMap'));
              if (arguments.length > 0) {
                throw new TypeError('WeakMap iterable is not supported');
              }
            }
            defineProperty(WeakMap.prototype, 'delete', function(key) {
              checkInstance(this, 'delete');
              if (!isObject(key)) {
                return false;
              }
              var entry = key[this._id];
              if (entry && entry[0] === key) {
                delete key[this._id];
                return true;
              }
              return false;
            });
            defineProperty(WeakMap.prototype, 'get', function(key) {
              checkInstance(this, 'get');
              if (!isObject(key)) {
                return void 0;
              }
              var entry = key[this._id];
              if (entry && entry[0] === key) {
                return entry[1];
              }
              return void 0;
            });
            defineProperty(WeakMap.prototype, 'has', function(key) {
              checkInstance(this, 'has');
              if (!isObject(key)) {
                return false;
              }
              var entry = key[this._id];
              if (entry && entry[0] === key) {
                return true;
              }
              return false;
            });
            defineProperty(WeakMap.prototype, 'set', function(key, value) {
              checkInstance(this, 'set');
              if (!isObject(key)) {
                throw new TypeError('Invalid value used as weak map key');
              }
              var entry = key[this._id];
              if (entry && entry[0] === key) {
                entry[1] = value;
                return this;
              }
              defineProperty(key, this._id, [ key, value ]);
              return this;
            });
            function checkInstance(x, methodName) {
              if (!isObject(x) || !hasOwnProperty.call(x, '_id')) {
                throw new TypeError(methodName + ' method called on incompatible receiver ' + typeof x);
              }
            }
            function genId(prefix) {
              return prefix + '_' + rand() + '.' + rand();
            }
            function rand() {
              return Math.random().toString().substring(2);
            }
            defineProperty(WeakMap, '_polyfill', true);
            return WeakMap;
          }();
          function isObject(x) {
            return Object(x) === x;
          }
        })(typeof self !== 'undefined' ? self : typeof window !== 'undefined' ? window : typeof global !== 'undefined' ? global : this);
      }).call(this, typeof global !== 'undefined' ? global : typeof self !== 'undefined' ? self : typeof window !== 'undefined' ? window : {});
    }, {} ]
  }, {}, [ 1 ]);
  'use strict';
  var utils = axe.utils = {};
  'use strict';
  var helpers = {};
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  var dotRegex = /\{\{.+?\}\}/g;
  function getDefaultConfiguration(audit) {
    'use strict';
    var config;
    if (audit) {
      config = axe.utils.clone(audit);
      config.commons = audit.commons;
    } else {
      config = {};
    }
    config.reporter = config.reporter || null;
    config.rules = config.rules || [];
    config.checks = config.checks || [];
    config.data = _extends({
      checks: {},
      rules: {}
    }, config.data);
    return config;
  }
  function unpackToObject(collection, audit, method) {
    'use strict';
    var i, l;
    for (i = 0, l = collection.length; i < l; i++) {
      audit[method](collection[i]);
    }
  }
  function Audit(audit) {
    this.brand = 'axe';
    this.application = 'axeAPI';
    this.tagExclude = [ 'experimental' ];
    this.lang = 'en';
    this.defaultConfig = audit;
    this._init();
    this._defaultLocale = null;
  }
  Audit.prototype._setDefaultLocale = function() {
    if (this._defaultLocale) {
      return;
    }
    var locale = {
      checks: {},
      rules: {},
      failureSummaries: {},
      incompleteFallbackMessage: '',
      lang: this.lang
    };
    var checkIDs = Object.keys(this.data.checks);
    for (var i = 0; i < checkIDs.length; i++) {
      var id = checkIDs[i];
      var check = this.data.checks[id];
      var _check$messages = check.messages, pass = _check$messages.pass, fail = _check$messages.fail, incomplete = _check$messages.incomplete;
      locale.checks[id] = {
        pass: pass,
        fail: fail,
        incomplete: incomplete
      };
    }
    var ruleIDs = Object.keys(this.data.rules);
    for (var _i = 0; _i < ruleIDs.length; _i++) {
      var _id = ruleIDs[_i];
      var rule = this.data.rules[_id];
      var description = rule.description, help = rule.help;
      locale.rules[_id] = {
        description: description,
        help: help
      };
    }
    var failureSummaries = Object.keys(this.data.failureSummaries);
    for (var _i2 = 0; _i2 < failureSummaries.length; _i2++) {
      var type = failureSummaries[_i2];
      var failureSummary = this.data.failureSummaries[type];
      var failureMessage = failureSummary.failureMessage;
      locale.failureSummaries[type] = {
        failureMessage: failureMessage
      };
    }
    locale.incompleteFallbackMessage = this.data.incompleteFallbackMessage;
    this._defaultLocale = locale;
  };
  Audit.prototype._resetLocale = function() {
    var defaultLocale = this._defaultLocale;
    if (!defaultLocale) {
      return;
    }
    this.applyLocale(defaultLocale);
  };
  var mergeCheckLocale = function mergeCheckLocale(a, b) {
    var pass = b.pass, fail = b.fail;
    if (typeof pass === 'string' && dotRegex.test(pass)) {
      pass = axe.imports.doT.compile(pass);
    }
    if (typeof fail === 'string' && dotRegex.test(fail)) {
      fail = axe.imports.doT.compile(fail);
    }
    return _extends({}, a, {
      messages: {
        pass: pass || a.messages.pass,
        fail: fail || a.messages.fail,
        incomplete: _typeof(a.messages.incomplete) === 'object' ? _extends({}, a.messages.incomplete, {}, b.incomplete) : b.incomplete
      }
    });
  };
  var mergeRuleLocale = function mergeRuleLocale(a, b) {
    var help = b.help, description = b.description;
    if (typeof help === 'string' && dotRegex.test(help)) {
      help = axe.imports.doT.compile(help);
    }
    if (typeof description === 'string' && dotRegex.test(description)) {
      description = axe.imports.doT.compile(description);
    }
    return _extends({}, a, {
      help: help || a.help,
      description: description || a.description
    });
  };
  var mergeFailureMessage = function mergeFailureMessage(a, b) {
    var failureMessage = b.failureMessage;
    if (typeof failureMessage === 'string' && dotRegex.test(failureMessage)) {
      failureMessage = axe.imports.doT.compile(failureMessage);
    }
    return _extends({}, a, {
      failureMessage: failureMessage || a.failureMessage
    });
  };
  var mergeFallbackMessage = function mergeFallbackMessage(a, b) {
    if (typeof b === 'string' && dotRegex.test(b)) {
      b = axe.imports.doT.compile(b);
    }
    return b || a;
  };
  Audit.prototype._applyCheckLocale = function(checks) {
    var keys = Object.keys(checks);
    for (var i = 0; i < keys.length; i++) {
      var id = keys[i];
      if (!this.data.checks[id]) {
        throw new Error('Locale provided for unknown check: "'.concat(id, '"'));
      }
      this.data.checks[id] = mergeCheckLocale(this.data.checks[id], checks[id]);
    }
  };
  Audit.prototype._applyRuleLocale = function(rules) {
    var keys = Object.keys(rules);
    for (var i = 0; i < keys.length; i++) {
      var id = keys[i];
      if (!this.data.rules[id]) {
        throw new Error('Locale provided for unknown rule: "'.concat(id, '"'));
      }
      this.data.rules[id] = mergeRuleLocale(this.data.rules[id], rules[id]);
    }
  };
  Audit.prototype._applyFailureSummaries = function(messages) {
    var keys = Object.keys(messages);
    for (var i = 0; i < keys.length; i++) {
      var key = keys[i];
      if (!this.data.failureSummaries[key]) {
        throw new Error('Locale provided for unknown failureMessage: "'.concat(key, '"'));
      }
      this.data.failureSummaries[key] = mergeFailureMessage(this.data.failureSummaries[key], messages[key]);
    }
  };
  Audit.prototype.applyLocale = function(locale) {
    this._setDefaultLocale();
    if (locale.checks) {
      this._applyCheckLocale(locale.checks);
    }
    if (locale.rules) {
      this._applyRuleLocale(locale.rules);
    }
    if (locale.failureSummaries) {
      this._applyFailureSummaries(locale.failureSummaries, 'failureSummaries');
    }
    if (locale.incompleteFallbackMessage) {
      this.data.incompleteFallbackMessage = mergeFallbackMessage(this.data.incompleteFallbackMessage, locale.incompleteFallbackMessage);
    }
    if (locale.lang) {
      this.lang = locale.lang;
    }
  };
  Audit.prototype._init = function() {
    var audit = getDefaultConfiguration(this.defaultConfig);
    axe.commons = commons = audit.commons;
    this.lang = audit.lang || 'en';
    this.reporter = audit.reporter;
    this.commands = {};
    this.rules = [];
    this.checks = {};
    unpackToObject(audit.rules, this, 'addRule');
    unpackToObject(audit.checks, this, 'addCheck');
    this.data = {};
    this.data.checks = audit.data && audit.data.checks || {};
    this.data.rules = audit.data && audit.data.rules || {};
    this.data.failureSummaries = audit.data && audit.data.failureSummaries || {};
    this.data.incompleteFallbackMessage = audit.data && audit.data.incompleteFallbackMessage || '';
    this._constructHelpUrls();
  };
  Audit.prototype.registerCommand = function(command) {
    'use strict';
    this.commands[command.id] = command.callback;
  };
  Audit.prototype.addRule = function(spec) {
    'use strict';
    if (spec.metadata) {
      this.data.rules[spec.id] = spec.metadata;
    }
    var rule = this.getRule(spec.id);
    if (rule) {
      rule.configure(spec);
    } else {
      this.rules.push(new Rule(spec, this));
    }
  };
  Audit.prototype.addCheck = function(spec) {
    'use strict';
    var metadata = spec.metadata;
    if (_typeof(metadata) === 'object') {
      this.data.checks[spec.id] = metadata;
      if (_typeof(metadata.messages) === 'object') {
        Object.keys(metadata.messages).filter(function(prop) {
          return metadata.messages.hasOwnProperty(prop) && typeof metadata.messages[prop] === 'string';
        }).forEach(function(prop) {
          if (metadata.messages[prop].indexOf('function') === 0) {
            metadata.messages[prop] = new Function('return ' + metadata.messages[prop] + ';')();
          }
        });
      }
    }
    if (this.checks[spec.id]) {
      this.checks[spec.id].configure(spec);
    } else {
      this.checks[spec.id] = new Check(spec);
    }
  };
  function getRulesToRun(rules, context, options) {
    var base = {
      now: [],
      later: []
    };
    var splitRules = rules.reduce(function(out, rule) {
      if (!axe.utils.ruleShouldRun(rule, context, options)) {
        return out;
      }
      if (rule.preload) {
        out.later.push(rule);
        return out;
      }
      out.now.push(rule);
      return out;
    }, base);
    return splitRules;
  }
  function getDefferedRule(rule, context, options) {
    if (options.performanceTimer) {
      axe.utils.performanceTimer.mark('mark_rule_start_' + rule.id);
    }
    return function(resolve, reject) {
      rule.run(context, options, function(ruleResult) {
        resolve(ruleResult);
      }, function(err) {
        if (!options.debug) {
          var errResult = Object.assign(new RuleResult(rule), {
            result: axe.constants.CANTTELL,
            description: 'An error occured while running this rule',
            message: err.message,
            stack: err.stack,
            error: err,
            errorNode: err.errorNode
          });
          resolve(errResult);
        } else {
          reject(err);
        }
      });
    };
  }
  Audit.prototype.run = function(context, options, resolve, reject) {
    'use strict';
    this.normalizeOptions(options);
    axe._selectCache = [];
    var allRulesToRun = getRulesToRun(this.rules, context, options);
    var runNowRules = allRulesToRun.now;
    var runLaterRules = allRulesToRun.later;
    var nowRulesQueue = axe.utils.queue();
    runNowRules.forEach(function(rule) {
      nowRulesQueue.defer(getDefferedRule(rule, context, options));
    });
    var preloaderQueue = axe.utils.queue();
    if (runLaterRules.length) {
      preloaderQueue.defer(function(resolve) {
        axe.utils.preload(options).then(function(assets) {
          return resolve(assets);
        })['catch'](function(err) {
          console.warn('Couldn\'t load preload assets: ', err);
          resolve(undefined);
        });
      });
    }
    var queueForNowRulesAndPreloader = axe.utils.queue();
    queueForNowRulesAndPreloader.defer(nowRulesQueue);
    queueForNowRulesAndPreloader.defer(preloaderQueue);
    queueForNowRulesAndPreloader.then(function(nowRulesAndPreloaderResults) {
      var assetsFromQueue = nowRulesAndPreloaderResults.pop();
      if (assetsFromQueue && assetsFromQueue.length) {
        var assets = assetsFromQueue[0];
        if (assets) {
          context = _extends({}, context, {}, assets);
        }
      }
      var nowRulesResults = nowRulesAndPreloaderResults[0];
      if (!runLaterRules.length) {
        axe._selectCache = undefined;
        resolve(nowRulesResults.filter(function(result) {
          return !!result;
        }));
        return;
      }
      var laterRulesQueue = axe.utils.queue();
      runLaterRules.forEach(function(rule) {
        var deferredRule = getDefferedRule(rule, context, options);
        laterRulesQueue.defer(deferredRule);
      });
      laterRulesQueue.then(function(laterRuleResults) {
        axe._selectCache = undefined;
        resolve(nowRulesResults.concat(laterRuleResults).filter(function(result) {
          return !!result;
        }));
      })['catch'](reject);
    })['catch'](reject);
  };
  Audit.prototype.after = function(results, options) {
    'use strict';
    var rules = this.rules;
    return results.map(function(ruleResult) {
      var rule = axe.utils.findBy(rules, 'id', ruleResult.id);
      if (!rule) {
        throw new Error('Result for unknown rule. You may be running mismatch axe-core versions');
      }
      return rule.after(ruleResult, options);
    });
  };
  Audit.prototype.getRule = function(ruleId) {
    return this.rules.find(function(rule) {
      return rule.id === ruleId;
    });
  };
  Audit.prototype.normalizeOptions = function(options) {
    'use strict';
    var audit = this;
    var tags = [];
    var ruleIds = [];
    audit.rules.forEach(function(rule) {
      ruleIds.push(rule.id);
      rule.tags.forEach(function(tag) {
        if (!tags.includes(tag)) {
          tags.push(tag);
        }
      });
    });
    if (_typeof(options.runOnly) === 'object') {
      if (Array.isArray(options.runOnly)) {
        var hasTag = options.runOnly.find(function(value) {
          return tags.includes(value);
        });
        var hasRule = options.runOnly.find(function(value) {
          return ruleIds.includes(value);
        });
        if (hasTag && hasRule) {
          throw new Error('runOnly cannot be both rules and tags');
        }
        if (hasRule) {
          options.runOnly = {
            type: 'rule',
            values: options.runOnly
          };
        } else {
          options.runOnly = {
            type: 'tag',
            values: options.runOnly
          };
        }
      }
      var only = options.runOnly;
      if (only.value && !only.values) {
        only.values = only.value;
        delete only.value;
      }
      if (!Array.isArray(only.values) || only.values.length === 0) {
        throw new Error('runOnly.values must be a non-empty array');
      }
      if ([ 'rule', 'rules' ].includes(only.type)) {
        only.type = 'rule';
        only.values.forEach(function(ruleId) {
          if (!ruleIds.includes(ruleId)) {
            throw new Error('unknown rule `' + ruleId + '` in options.runOnly');
          }
        });
      } else if ([ 'tag', 'tags', undefined ].includes(only.type)) {
        only.type = 'tag';
        var unmatchedTags = only.values.filter(function(tag) {
          return !tags.includes(tag);
        });
        if (unmatchedTags.length !== 0) {
          axe.log('Could not find tags `' + unmatchedTags.join('`, `') + '`');
        }
      } else {
        throw new Error('Unknown runOnly type \''.concat(only.type, '\''));
      }
    }
    if (_typeof(options.rules) === 'object') {
      Object.keys(options.rules).forEach(function(ruleId) {
        if (!ruleIds.includes(ruleId)) {
          throw new Error('unknown rule `' + ruleId + '` in options.rules');
        }
      });
    }
    return options;
  };
  Audit.prototype.setBranding = function(branding) {
    'use strict';
    var previous = {
      brand: this.brand,
      application: this.application
    };
    if (branding && branding.hasOwnProperty('brand') && branding.brand && typeof branding.brand === 'string') {
      this.brand = branding.brand;
    }
    if (branding && branding.hasOwnProperty('application') && branding.application && typeof branding.application === 'string') {
      this.application = branding.application;
    }
    this._constructHelpUrls(previous);
  };
  function getHelpUrl(_ref, ruleId, version) {
    var brand = _ref.brand, application = _ref.application, lang = _ref.lang;
    return axe.constants.helpUrlBase + brand + '/' + (version || axe.version.substring(0, axe.version.lastIndexOf('.'))) + '/' + ruleId + '?application=' + encodeURIComponent(application) + (lang && lang !== 'en' ? '&lang=' + encodeURIComponent(lang) : '');
  }
  Audit.prototype._constructHelpUrls = function() {
    var _this = this;
    var previous = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : null;
    var version = (axe.version.match(/^[1-9][0-9]*\.[0-9]+/) || [ 'x.y' ])[0];
    this.rules.forEach(function(rule) {
      if (!_this.data.rules[rule.id]) {
        _this.data.rules[rule.id] = {};
      }
      var metaData = _this.data.rules[rule.id];
      if (typeof metaData.helpUrl !== 'string' || previous && metaData.helpUrl === getHelpUrl(previous, rule.id, version)) {
        metaData.helpUrl = getHelpUrl(_this, rule.id, version);
      }
    });
  };
  Audit.prototype.resetRulesAndChecks = function() {
    'use strict';
    this._init();
    this._resetLocale();
  };
  'use strict';
  (function() {
    'use strict';
    var _cache = {};
    var cache = {
      set: function set(key, value) {
        _cache[key] = value;
      },
      get: function get(key) {
        return _cache[key];
      },
      clear: function clear() {
        _cache = {};
      }
    };
    axe._cache = cache;
  })();
  'use strict';
  function CheckResult(check) {
    'use strict';
    this.id = check.id;
    this.data = null;
    this.relatedNodes = [];
    this.result = null;
  }
  'use strict';
  function createExecutionContext(spec) {
    'use strict';
    if (typeof spec === 'string') {
      return new Function('return ' + spec + ';')();
    }
    return spec;
  }
  function Check(spec) {
    if (spec) {
      this.id = spec.id;
      this.configure(spec);
    }
  }
  Check.prototype.enabled = true;
  Check.prototype.run = function(node, options, context, resolve, reject) {
    'use strict';
    options = options || {};
    var enabled = options.hasOwnProperty('enabled') ? options.enabled : this.enabled, checkOptions = options.options || this.options;
    if (enabled) {
      var checkResult = new CheckResult(this);
      var checkHelper = axe.utils.checkHelper(checkResult, options, resolve, reject);
      var result;
      try {
        result = this.evaluate.call(checkHelper, node.actualNode, checkOptions, node, context);
      } catch (e) {
        if (node && node.actualNode) {
          e.errorNode = new DqElement(node.actualNode).toJSON();
        }
        reject(e);
        return;
      }
      if (!checkHelper.isAsync) {
        checkResult.result = result;
        resolve(checkResult);
      }
    } else {
      resolve(null);
    }
  };
  Check.prototype.runSync = function(node, options, context) {
    options = options || {};
    var _options = options, _options$enabled = _options.enabled, enabled = _options$enabled === void 0 ? this.enabled : _options$enabled;
    if (!enabled) {
      return null;
    }
    var checkOptions = options.options || this.options;
    var checkResult = new CheckResult(this);
    var checkHelper = axe.utils.checkHelper(checkResult, options);
    checkHelper.async = function() {
      throw new Error('Cannot run async check while in a synchronous run');
    };
    var result;
    try {
      result = this.evaluate.call(checkHelper, node.actualNode, checkOptions, node, context);
    } catch (e) {
      if (node && node.actualNode) {
        e.errorNode = new DqElement(node.actualNode).toJSON();
      }
      throw e;
    }
    checkResult.result = result;
    return checkResult;
  };
  Check.prototype.configure = function(spec) {
    var _this = this;
    [ 'options', 'enabled' ].filter(function(prop) {
      return spec.hasOwnProperty(prop);
    }).forEach(function(prop) {
      return _this[prop] = spec[prop];
    });
    [ 'evaluate', 'after' ].filter(function(prop) {
      return spec.hasOwnProperty(prop);
    }).forEach(function(prop) {
      return _this[prop] = createExecutionContext(spec[prop]);
    });
  };
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  function pushUniqueFrame(collection, frame) {
    'use strict';
    if (axe.utils.isHidden(frame)) {
      return;
    }
    var fr = axe.utils.findBy(collection, 'node', frame);
    if (!fr) {
      collection.push({
        node: frame,
        include: [],
        exclude: []
      });
    }
  }
  function pushUniqueFrameSelector(context, type, selectorArray) {
    'use strict';
    context.frames = context.frames || [];
    var result, frame;
    var frames = document.querySelectorAll(selectorArray.shift());
    frameloop: for (var i = 0, l = frames.length; i < l; i++) {
      frame = frames[i];
      for (var j = 0, l2 = context.frames.length; j < l2; j++) {
        if (context.frames[j].node === frame) {
          context.frames[j][type].push(selectorArray);
          break frameloop;
        }
      }
      result = {
        node: frame,
        include: [],
        exclude: []
      };
      if (selectorArray) {
        result[type].push(selectorArray);
      }
      context.frames.push(result);
    }
  }
  function normalizeContext(context) {
    'use strict';
    if (context && _typeof(context) === 'object' || context instanceof NodeList) {
      if (context instanceof Node) {
        return {
          include: [ context ],
          exclude: []
        };
      }
      if (context.hasOwnProperty('include') || context.hasOwnProperty('exclude')) {
        return {
          include: context.include && +context.include.length ? context.include : [ document ],
          exclude: context.exclude || []
        };
      }
      if (context.length === +context.length) {
        return {
          include: context,
          exclude: []
        };
      }
    }
    if (typeof context === 'string') {
      return {
        include: [ context ],
        exclude: []
      };
    }
    return {
      include: [ document ],
      exclude: []
    };
  }
  function parseSelectorArray(context, type) {
    'use strict';
    var item, result = [], nodeList;
    for (var i = 0, l = context[type].length; i < l; i++) {
      item = context[type][i];
      if (typeof item === 'string') {
        nodeList = Array.from(document.querySelectorAll(item));
        result = result.concat(nodeList.map(function(node) {
          return axe.utils.getNodeFromTree(node);
        }));
        break;
      } else if (item && item.length && !(item instanceof Node)) {
        if (item.length > 1) {
          pushUniqueFrameSelector(context, type, item);
        } else {
          nodeList = Array.from(document.querySelectorAll(item[0]));
          result = result.concat(nodeList.map(function(node) {
            return axe.utils.getNodeFromTree(node);
          }));
        }
      } else if (item instanceof Node) {
        if (item.documentElement instanceof Node) {
          result.push(context.flatTree[0]);
        } else {
          result.push(axe.utils.getNodeFromTree(item));
        }
      }
    }
    return result.filter(function(r) {
      return r;
    });
  }
  function validateContext(context) {
    'use strict';
    if (context.include.length === 0) {
      if (context.frames.length === 0) {
        var env = axe.utils.respondable.isInFrame() ? 'frame' : 'page';
        return new Error('No elements found for include in ' + env + ' Context');
      }
      context.frames.forEach(function(frame, i) {
        if (frame.include.length === 0) {
          return new Error('No elements found for include in Context of frame ' + i);
        }
      });
    }
  }
  function getRootNode(_ref) {
    var include = _ref.include, exclude = _ref.exclude;
    var selectors = Array.from(include).concat(Array.from(exclude));
    for (var i = 0; i < selectors.length; ++i) {
      var item = selectors[i];
      if (item instanceof Element) {
        return item.ownerDocument.documentElement;
      }
      if (item instanceof Document) {
        return item.documentElement;
      }
    }
    return document.documentElement;
  }
  function Context(spec) {
    'use strict';
    var _this = this;
    this.frames = [];
    this.initiator = spec && typeof spec.initiator === 'boolean' ? spec.initiator : true;
    this.page = false;
    spec = normalizeContext(spec);
    this.flatTree = axe.utils.getFlattenedTree(getRootNode(spec));
    this.exclude = spec.exclude;
    this.include = spec.include;
    this.include = parseSelectorArray(this, 'include');
    this.exclude = parseSelectorArray(this, 'exclude');
    axe.utils.select('frame, iframe', this).forEach(function(frame) {
      if (isNodeInContext(frame, _this)) {
        pushUniqueFrame(_this.frames, frame.actualNode);
      }
    });
    if (this.include.length === 1 && this.include[0].actualNode === document.documentElement) {
      this.page = true;
    }
    var err = validateContext(this);
    if (err instanceof Error) {
      throw err;
    }
    if (!Array.isArray(this.include)) {
      this.include = Array.from(this.include);
    }
    this.include.sort(axe.utils.nodeSorter);
  }
  'use strict';
  function RuleResult(rule) {
    'use strict';
    this.id = rule.id;
    this.result = axe.constants.NA;
    this.pageLevel = rule.pageLevel;
    this.impact = null;
    this.nodes = [];
  }
  'use strict';
  function Rule(spec, parentAudit) {
    'use strict';
    this._audit = parentAudit;
    this.id = spec.id;
    this.selector = spec.selector || '*';
    this.excludeHidden = typeof spec.excludeHidden === 'boolean' ? spec.excludeHidden : true;
    this.enabled = typeof spec.enabled === 'boolean' ? spec.enabled : true;
    this.pageLevel = typeof spec.pageLevel === 'boolean' ? spec.pageLevel : false;
    this.any = spec.any || [];
    this.all = spec.all || [];
    this.none = spec.none || [];
    this.tags = spec.tags || [];
    this.preload = spec.preload ? true : false;
    if (spec.matches) {
      this.matches = createExecutionContext(spec.matches);
    }
  }
  Rule.prototype.matches = function() {
    'use strict';
    return true;
  };
  Rule.prototype.gather = function(context) {
    var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
    var markStart = 'mark_gather_start_' + this.id;
    var markEnd = 'mark_gather_end_' + this.id;
    var markHiddenStart = 'mark_isHidden_start_' + this.id;
    var markHiddenEnd = 'mark_isHidden_end_' + this.id;
    if (options.performanceTimer) {
      axe.utils.performanceTimer.mark(markStart);
    }
    var elements = axe.utils.select(this.selector, context);
    if (this.excludeHidden) {
      if (options.performanceTimer) {
        axe.utils.performanceTimer.mark(markHiddenStart);
      }
      elements = elements.filter(function(element) {
        return !axe.utils.isHidden(element.actualNode);
      });
      if (options.performanceTimer) {
        axe.utils.performanceTimer.mark(markHiddenEnd);
        axe.utils.performanceTimer.measure('rule_' + this.id + '#gather_axe.utils.isHidden', markHiddenStart, markHiddenEnd);
      }
    }
    if (options.performanceTimer) {
      axe.utils.performanceTimer.mark(markEnd);
      axe.utils.performanceTimer.measure('rule_' + this.id + '#gather', markStart, markEnd);
    }
    return elements;
  };
  Rule.prototype.runChecks = function(type, node, options, context, resolve, reject) {
    'use strict';
    var self = this;
    var checkQueue = axe.utils.queue();
    this[type].forEach(function(c) {
      var check = self._audit.checks[c.id || c];
      var option = axe.utils.getCheckOption(check, self.id, options);
      checkQueue.defer(function(res, rej) {
        check.run(node, option, context, res, rej);
      });
    });
    checkQueue.then(function(results) {
      results = results.filter(function(check) {
        return check;
      });
      resolve({
        type: type,
        results: results
      });
    })['catch'](reject);
  };
  Rule.prototype.runChecksSync = function(type, node, options, context) {
    'use strict';
    var self = this;
    var results = [];
    this[type].forEach(function(c) {
      var check = self._audit.checks[c.id || c];
      var option = axe.utils.getCheckOption(check, self.id, options);
      results.push(check.runSync(node, option, context));
    });
    results = results.filter(function(check) {
      return check;
    });
    return {
      type: type,
      results: results
    };
  };
  Rule.prototype.run = function(context) {
    var _this = this;
    var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
    var resolve = arguments.length > 2 ? arguments[2] : undefined;
    var reject = arguments.length > 3 ? arguments[3] : undefined;
    if (options.performanceTimer) {
      this._trackPerformance();
    }
    var q = axe.utils.queue();
    var ruleResult = new RuleResult(this);
    var nodes;
    try {
      nodes = this.gatherAndMatchNodes(context, options);
    } catch (error) {
      reject(new SupportError({
        cause: error,
        ruleId: this.id
      }));
      return;
    }
    if (options.performanceTimer) {
      this._logGatherPerformance(nodes);
    }
    nodes.forEach(function(node) {
      q.defer(function(resolveNode, rejectNode) {
        var checkQueue = axe.utils.queue();
        [ 'any', 'all', 'none' ].forEach(function(type) {
          checkQueue.defer(function(res, rej) {
            _this.runChecks(type, node, options, context, res, rej);
          });
        });
        checkQueue.then(function(results) {
          var result = getResult(results);
          if (result) {
            result.node = new axe.utils.DqElement(node.actualNode, options);
            ruleResult.nodes.push(result);
          }
          resolveNode();
        })['catch'](function(err) {
          return rejectNode(err);
        });
      });
    });
    q.defer(function(resolve) {
      return setTimeout(resolve, 0);
    });
    if (options.performanceTimer) {
      this._logRulePerformance();
    }
    q.then(function() {
      return resolve(ruleResult);
    })['catch'](function(error) {
      return reject(error);
    });
  };
  Rule.prototype.runSync = function(context) {
    var _this2 = this;
    var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
    if (options.performanceTimer) {
      this._trackPerformance();
    }
    var ruleResult = new RuleResult(this);
    var nodes;
    try {
      nodes = this.gatherAndMatchNodes(context, options);
    } catch (error) {
      throw new SupportError({
        cause: error,
        ruleId: this.id
      });
    }
    if (options.performanceTimer) {
      this._logGatherPerformance(nodes);
    }
    nodes.forEach(function(node) {
      var results = [];
      [ 'any', 'all', 'none' ].forEach(function(type) {
        results.push(_this2.runChecksSync(type, node, options, context));
      });
      var result = getResult(results);
      if (result) {
        result.node = node.actualNode ? new axe.utils.DqElement(node.actualNode, options) : null;
        ruleResult.nodes.push(result);
      }
    });
    if (options.performanceTimer) {
      this._logRulePerformance();
    }
    return ruleResult;
  };
  Rule.prototype._trackPerformance = function() {
    this._markStart = 'mark_rule_start_' + this.id;
    this._markEnd = 'mark_rule_end_' + this.id;
    this._markChecksStart = 'mark_runchecks_start_' + this.id;
    this._markChecksEnd = 'mark_runchecks_end_' + this.id;
  };
  Rule.prototype._logGatherPerformance = function(nodes) {
    axe.log('gather (', nodes.length, '):', axe.utils.performanceTimer.timeElapsed() + 'ms');
    axe.utils.performanceTimer.mark(this._markChecksStart);
  };
  Rule.prototype._logRulePerformance = function() {
    axe.utils.performanceTimer.mark(this._markChecksEnd);
    axe.utils.performanceTimer.mark(this._markEnd);
    axe.utils.performanceTimer.measure('runchecks_' + this.id, this._markChecksStart, this._markChecksEnd);
    axe.utils.performanceTimer.measure('rule_' + this.id, this._markStart, this._markEnd);
  };
  function getResult(results) {
    if (results.length) {
      var hasResults = false, result = {};
      results.forEach(function(r) {
        var res = r.results.filter(function(result) {
          return result;
        });
        result[r.type] = res;
        if (res.length) {
          hasResults = true;
        }
      });
      if (hasResults) {
        return result;
      }
      return null;
    }
  }
  Rule.prototype.gatherAndMatchNodes = function(context, options) {
    var _this3 = this;
    var markMatchesStart = 'mark_matches_start_' + this.id;
    var markMatchesEnd = 'mark_matches_end_' + this.id;
    var nodes = this.gather(context, options);
    if (options.performanceTimer) {
      axe.utils.performanceTimer.mark(markMatchesStart);
    }
    nodes = nodes.filter(function(node) {
      return _this3.matches(node.actualNode, node, context);
    });
    if (options.performanceTimer) {
      axe.utils.performanceTimer.mark(markMatchesEnd);
      axe.utils.performanceTimer.measure('rule_' + this.id + '#matches', markMatchesStart, markMatchesEnd);
    }
    return nodes;
  };
  function findAfterChecks(rule) {
    'use strict';
    return axe.utils.getAllChecks(rule).map(function(c) {
      var check = rule._audit.checks[c.id || c];
      return check && typeof check.after === 'function' ? check : null;
    }).filter(Boolean);
  }
  function findCheckResults(nodes, checkID) {
    'use strict';
    var checkResults = [];
    nodes.forEach(function(nodeResult) {
      var checks = axe.utils.getAllChecks(nodeResult);
      checks.forEach(function(checkResult) {
        if (checkResult.id === checkID) {
          checkResults.push(checkResult);
        }
      });
    });
    return checkResults;
  }
  function filterChecks(checks) {
    'use strict';
    return checks.filter(function(check) {
      return check.filtered !== true;
    });
  }
  function sanitizeNodes(result) {
    'use strict';
    var checkTypes = [ 'any', 'all', 'none' ];
    var nodes = result.nodes.filter(function(detail) {
      var length = 0;
      checkTypes.forEach(function(type) {
        detail[type] = filterChecks(detail[type]);
        length += detail[type].length;
      });
      return length > 0;
    });
    if (result.pageLevel && nodes.length) {
      nodes = [ nodes.reduce(function(a, b) {
        if (a) {
          checkTypes.forEach(function(type) {
            a[type].push.apply(a[type], b[type]);
          });
          return a;
        }
      }) ];
    }
    return nodes;
  }
  Rule.prototype.after = function(result, options) {
    'use strict';
    var afterChecks = findAfterChecks(this);
    var ruleID = this.id;
    afterChecks.forEach(function(check) {
      var beforeResults = findCheckResults(result.nodes, check.id);
      var option = axe.utils.getCheckOption(check, ruleID, options);
      var afterResults = check.after(beforeResults, option);
      beforeResults.forEach(function(item) {
        if (afterResults.indexOf(item) === -1) {
          item.filtered = true;
        }
      });
    });
    result.nodes = sanitizeNodes(result);
    return result;
  };
  Rule.prototype.configure = function(spec) {
    'use strict';
    if (spec.hasOwnProperty('selector')) {
      this.selector = spec.selector;
    }
    if (spec.hasOwnProperty('excludeHidden')) {
      this.excludeHidden = typeof spec.excludeHidden === 'boolean' ? spec.excludeHidden : true;
    }
    if (spec.hasOwnProperty('enabled')) {
      this.enabled = typeof spec.enabled === 'boolean' ? spec.enabled : true;
    }
    if (spec.hasOwnProperty('pageLevel')) {
      this.pageLevel = typeof spec.pageLevel === 'boolean' ? spec.pageLevel : false;
    }
    if (spec.hasOwnProperty('any')) {
      this.any = spec.any;
    }
    if (spec.hasOwnProperty('all')) {
      this.all = spec.all;
    }
    if (spec.hasOwnProperty('none')) {
      this.none = spec.none;
    }
    if (spec.hasOwnProperty('tags')) {
      this.tags = spec.tags;
    }
    if (spec.hasOwnProperty('matches')) {
      if (typeof spec.matches === 'string') {
        this.matches = new Function('return ' + spec.matches + ';')();
      } else {
        this.matches = spec.matches;
      }
    }
  };
  'use strict';
  function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
      throw new TypeError('Cannot call a class as a function');
    }
  }
  function _defineProperties(target, props) {
    for (var i = 0; i < props.length; i++) {
      var descriptor = props[i];
      descriptor.enumerable = descriptor.enumerable || false;
      descriptor.configurable = true;
      if ('value' in descriptor) {
        descriptor.writable = true;
      }
      Object.defineProperty(target, descriptor.key, descriptor);
    }
  }
  function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) {
      _defineProperties(Constructor.prototype, protoProps);
    }
    if (staticProps) {
      _defineProperties(Constructor, staticProps);
    }
    return Constructor;
  }
  var whitespaceRegex = /[\t\r\n\f]/g;
  var AbstractVirtualNode = function() {
    function AbstractVirtualNode() {
      _classCallCheck(this, AbstractVirtualNode);
      this.children = [];
      this.parent = null;
    }
    _createClass(AbstractVirtualNode, [ {
      key: 'attr',
      value: function attr() {
        throw new Error('VirtualNode class must have a "attr" function');
      }
    }, {
      key: 'hasAttr',
      value: function hasAttr() {
        throw new Error('VirtualNode class must have a "hasAttr" function');
      }
    }, {
      key: 'hasClass',
      value: function hasClass(className) {
        var classAttr = this.attr('class');
        if (!classAttr) {
          return false;
        }
        var selector = ' ' + className + ' ';
        return (' ' + classAttr + ' ').replace(whitespaceRegex, ' ').indexOf(selector) >= 0;
      }
    }, {
      key: 'props',
      get: function get() {
        throw new Error('VirtualNode class must have a "props" object consisting ' + 'of "nodeType" and "nodeName" properties');
      }
    } ]);
    return AbstractVirtualNode;
  }();
  axe.AbstractVirtualNode = AbstractVirtualNode;
  'use strict';
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
      throw new TypeError('Cannot call a class as a function');
    }
  }
  function _defineProperties(target, props) {
    for (var i = 0; i < props.length; i++) {
      var descriptor = props[i];
      descriptor.enumerable = descriptor.enumerable || false;
      descriptor.configurable = true;
      if ('value' in descriptor) {
        descriptor.writable = true;
      }
      Object.defineProperty(target, descriptor.key, descriptor);
    }
  }
  function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) {
      _defineProperties(Constructor.prototype, protoProps);
    }
    if (staticProps) {
      _defineProperties(Constructor, staticProps);
    }
    return Constructor;
  }
  function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === 'object' || typeof call === 'function')) {
      return call;
    }
    return _assertThisInitialized(self);
  }
  function _assertThisInitialized(self) {
    if (self === void 0) {
      throw new ReferenceError('this hasn\'t been initialised - super() hasn\'t been called');
    }
    return self;
  }
  function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf : function _getPrototypeOf(o) {
      return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
  }
  function _inherits(subClass, superClass) {
    if (typeof superClass !== 'function' && superClass !== null) {
      throw new TypeError('Super expression must either be null or a function');
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
      constructor: {
        value: subClass,
        writable: true,
        configurable: true
      }
    });
    if (superClass) {
      _setPrototypeOf(subClass, superClass);
    }
  }
  function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf || function _setPrototypeOf(o, p) {
      o.__proto__ = p;
      return o;
    };
    return _setPrototypeOf(o, p);
  }
  var SerialVirtualNode = function(_axe$AbstractVirtualN) {
    _inherits(SerialVirtualNode, _axe$AbstractVirtualN);
    function SerialVirtualNode(serialNode) {
      var _this;
      _classCallCheck(this, SerialVirtualNode);
      _this = _possibleConstructorReturn(this, _getPrototypeOf(SerialVirtualNode).call(this));
      _this._props = normaliseProps(serialNode);
      _this._attrs = normaliseAttrs(serialNode);
      return _this;
    }
    _createClass(SerialVirtualNode, [ {
      key: 'attr',
      value: function attr(attrName) {
        return this._attrs[attrName] || null;
      }
    }, {
      key: 'hasAttr',
      value: function hasAttr(attrName) {
        return this._attrs[attrName] !== undefined;
      }
    }, {
      key: 'props',
      get: function get() {
        return this._props;
      }
    } ]);
    return SerialVirtualNode;
  }(axe.AbstractVirtualNode);
  function normaliseProps(serialNode) {
    var nodeName = serialNode.nodeName, _serialNode$nodeType = serialNode.nodeType, nodeType = _serialNode$nodeType === void 0 ? 1 : _serialNode$nodeType;
    axe.utils.assert(nodeType === 1, 'nodeType has to be undefined or 1, got \''.concat(nodeType, '\''));
    axe.utils.assert(typeof nodeName === 'string', 'nodeName has to be a string, got \''.concat(nodeName, '\''));
    var props = _extends({}, serialNode, {
      nodeType: nodeType,
      nodeName: nodeName.toLowerCase()
    });
    delete props.attributes;
    return Object.freeze(props);
  }
  function normaliseAttrs(_ref) {
    var _ref$attributes = _ref.attributes, attributes = _ref$attributes === void 0 ? {} : _ref$attributes;
    var attrMap = {
      htmlFor: 'for',
      className: 'class'
    };
    return Object.keys(attributes).reduce(function(attrs, attrName) {
      var value = attributes[attrName];
      axe.utils.assert(_typeof(value) !== 'object' || value === null, 'expects attributes not to be an object, \''.concat(attrName, '\' was'));
      if (value !== undefined) {
        var mappedName = attrMap[attrName] || attrName;
        attrs[mappedName] = value !== null ? String(value) : null;
      }
      return attrs;
    }, {});
  }
  axe.SerialVirtualNode = SerialVirtualNode;
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  function _classCallCheck(instance, Constructor) {
    if (!(instance instanceof Constructor)) {
      throw new TypeError('Cannot call a class as a function');
    }
  }
  function _defineProperties(target, props) {
    for (var i = 0; i < props.length; i++) {
      var descriptor = props[i];
      descriptor.enumerable = descriptor.enumerable || false;
      descriptor.configurable = true;
      if ('value' in descriptor) {
        descriptor.writable = true;
      }
      Object.defineProperty(target, descriptor.key, descriptor);
    }
  }
  function _createClass(Constructor, protoProps, staticProps) {
    if (protoProps) {
      _defineProperties(Constructor.prototype, protoProps);
    }
    if (staticProps) {
      _defineProperties(Constructor, staticProps);
    }
    return Constructor;
  }
  function _possibleConstructorReturn(self, call) {
    if (call && (_typeof(call) === 'object' || typeof call === 'function')) {
      return call;
    }
    return _assertThisInitialized(self);
  }
  function _getPrototypeOf(o) {
    _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf : function _getPrototypeOf(o) {
      return o.__proto__ || Object.getPrototypeOf(o);
    };
    return _getPrototypeOf(o);
  }
  function _assertThisInitialized(self) {
    if (self === void 0) {
      throw new ReferenceError('this hasn\'t been initialised - super() hasn\'t been called');
    }
    return self;
  }
  function _inherits(subClass, superClass) {
    if (typeof superClass !== 'function' && superClass !== null) {
      throw new TypeError('Super expression must either be null or a function');
    }
    subClass.prototype = Object.create(superClass && superClass.prototype, {
      constructor: {
        value: subClass,
        writable: true,
        configurable: true
      }
    });
    if (superClass) {
      _setPrototypeOf(subClass, superClass);
    }
  }
  function _setPrototypeOf(o, p) {
    _setPrototypeOf = Object.setPrototypeOf || function _setPrototypeOf(o, p) {
      o.__proto__ = p;
      return o;
    };
    return _setPrototypeOf(o, p);
  }
  var isXHTMLGlobal;
  var VirtualNode = function(_axe$AbstractVirtualN) {
    _inherits(VirtualNode, _axe$AbstractVirtualN);
    function VirtualNode(node, parent, shadowId) {
      var _this;
      _classCallCheck(this, VirtualNode);
      _this = _possibleConstructorReturn(this, _getPrototypeOf(VirtualNode).call(this));
      _this.shadowId = shadowId;
      _this.children = [];
      _this.actualNode = node;
      _this.parent = parent;
      _this._isHidden = null;
      _this._cache = {};
      if (typeof isXHTMLGlobal === 'undefined') {
        isXHTMLGlobal = axe.utils.isXHTML(node.ownerDocument);
      }
      _this._isXHTML = isXHTMLGlobal;
      if (axe._cache.get('nodeMap')) {
        axe._cache.get('nodeMap').set(node, _assertThisInitialized(_this));
      }
      return _this;
    }
    _createClass(VirtualNode, [ {
      key: 'attr',
      value: function attr(attrName) {
        if (typeof this.actualNode.getAttribute !== 'function') {
          return null;
        }
        return this.actualNode.getAttribute(attrName);
      }
    }, {
      key: 'hasAttr',
      value: function hasAttr(attrName) {
        if (typeof this.actualNode.hasAttribute !== 'function') {
          return false;
        }
        return this.actualNode.hasAttribute(attrName);
      }
    }, {
      key: 'getComputedStylePropertyValue',
      value: function getComputedStylePropertyValue(property) {
        var key = 'computedStyle_' + property;
        if (!this._cache.hasOwnProperty(key)) {
          if (!this._cache.hasOwnProperty('computedStyle')) {
            this._cache.computedStyle = window.getComputedStyle(this.actualNode);
          }
          this._cache[key] = this._cache.computedStyle.getPropertyValue(property);
        }
        return this._cache[key];
      }
    }, {
      key: 'props',
      get: function get() {
        var _this$actualNode = this.actualNode, nodeType = _this$actualNode.nodeType, nodeName = _this$actualNode.nodeName, id = _this$actualNode.id, type = _this$actualNode.type, multiple = _this$actualNode.multiple;
        return {
          nodeType: nodeType,
          nodeName: this._isXHTML ? nodeName : nodeName.toLowerCase(),
          id: id,
          type: type,
          multiple: multiple
        };
      }
    }, {
      key: 'isFocusable',
      get: function get() {
        if (!this._cache.hasOwnProperty('isFocusable')) {
          this._cache.isFocusable = axe.commons.dom.isFocusable(this.actualNode);
        }
        return this._cache.isFocusable;
      }
    }, {
      key: 'tabbableElements',
      get: function get() {
        if (!this._cache.hasOwnProperty('tabbableElements')) {
          this._cache.tabbableElements = axe.commons.dom.getTabbableElements(this);
        }
        return this._cache.tabbableElements;
      }
    }, {
      key: 'clientRects',
      get: function get() {
        if (!this._cache.hasOwnProperty('clientRects')) {
          this._cache.clientRects = Array.from(this.actualNode.getClientRects()).filter(function(rect) {
            return rect.width > 0;
          });
        }
        return this._cache.clientRects;
      }
    }, {
      key: 'boundingClientRect',
      get: function get() {
        if (!this._cache.hasOwnProperty('boundingClientRect')) {
          this._cache.boundingClientRect = this.actualNode.getBoundingClientRect();
        }
        return this._cache.boundingClientRect;
      }
    } ]);
    return VirtualNode;
  }(axe.AbstractVirtualNode);
  axe.VirtualNode = VirtualNode;
  'use strict';
  (function(axe) {
    var definitions = [ {
      name: 'NA',
      value: 'inapplicable',
      priority: 0,
      group: 'inapplicable'
    }, {
      name: 'PASS',
      value: 'passed',
      priority: 1,
      group: 'passes'
    }, {
      name: 'CANTTELL',
      value: 'cantTell',
      priority: 2,
      group: 'incomplete'
    }, {
      name: 'FAIL',
      value: 'failed',
      priority: 3,
      group: 'violations'
    } ];
    var constants = {
      helpUrlBase: 'https://dequeuniversity.com/rules/',
      results: [],
      resultGroups: [],
      resultGroupMap: {},
      impact: Object.freeze([ 'minor', 'moderate', 'serious', 'critical' ]),
      preload: Object.freeze({
        assets: [ 'cssom', 'media' ],
        timeout: 1e4
      })
    };
    definitions.forEach(function(definition) {
      var name = definition.name;
      var value = definition.value;
      var priority = definition.priority;
      var group = definition.group;
      constants[name] = value;
      constants[name + '_PRIO'] = priority;
      constants[name + '_GROUP'] = group;
      constants.results[priority] = value;
      constants.resultGroups[priority] = group;
      constants.resultGroupMap[value] = group;
    });
    Object.freeze(constants.results);
    Object.freeze(constants.resultGroups);
    Object.freeze(constants.resultGroupMap);
    Object.freeze(constants);
    Object.defineProperty(axe, 'constants', {
      value: constants,
      enumerable: true,
      configurable: false,
      writable: false
    });
  })(axe);
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  axe.log = function() {
    'use strict';
    if ((typeof console === 'undefined' ? 'undefined' : _typeof(console)) === 'object' && console.log) {
      Function.prototype.apply.call(console.log, console, arguments);
    }
  };
  'use strict';
  function cleanupPlugins(resolve, reject) {
    'use strict';
    resolve = resolve || function() {};
    reject = reject || axe.log;
    if (!axe._audit) {
      throw new Error('No audit configured');
    }
    var q = axe.utils.queue();
    var cleanupErrors = [];
    Object.keys(axe.plugins).forEach(function(key) {
      q.defer(function(res) {
        var rej = function rej(err) {
          cleanupErrors.push(err);
          res();
        };
        try {
          axe.plugins[key].cleanup(res, rej);
        } catch (err) {
          rej(err);
        }
      });
    });
    var flattenedTree = axe.utils.getFlattenedTree(document.body);
    axe.utils.querySelectorAll(flattenedTree, 'iframe, frame').forEach(function(node) {
      q.defer(function(res, rej) {
        return axe.utils.sendCommandToFrame(node.actualNode, {
          command: 'cleanup-plugin'
        }, res, rej);
      });
    });
    q.then(function(results) {
      if (cleanupErrors.length === 0) {
        resolve(results);
      } else {
        reject(cleanupErrors);
      }
    })['catch'](reject);
  }
  axe.cleanup = cleanupPlugins;
  'use strict';
  function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _nonIterableRest();
  }
  function _nonIterableRest() {
    throw new TypeError('Invalid attempt to destructure non-iterable instance');
  }
  function _iterableToArrayLimit(arr, i) {
    if (!(Symbol.iterator in Object(arr) || Object.prototype.toString.call(arr) === '[object Arguments]')) {
      return;
    }
    var _arr = [];
    var _n = true;
    var _d = false;
    var _e = undefined;
    try {
      for (var _i = arr[Symbol.iterator](), _s; !(_n = (_s = _i.next()).done); _n = true) {
        _arr.push(_s.value);
        if (i && _arr.length === i) {
          break;
        }
      }
    } catch (err) {
      _d = true;
      _e = err;
    } finally {
      try {
        if (!_n && _i['return'] != null) {
          _i['return']();
        }
      } finally {
        if (_d) {
          throw _e;
        }
      }
    }
    return _arr;
  }
  function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) {
      return arr;
    }
  }
  function configureChecksRulesAndBranding(spec) {
    'use strict';
    var audit;
    audit = axe._audit;
    if (!audit) {
      throw new Error('No audit configured');
    }
    if (spec.axeVersion || spec.ver) {
      var specVersion = spec.axeVersion || spec.ver;
      if (!/^\d+\.\d+\.\d+(-canary)?/.test(specVersion)) {
        throw new Error('Invalid configured version '.concat(specVersion));
      }
      var _specVersion$split = specVersion.split('-'), _specVersion$split2 = _slicedToArray(_specVersion$split, 2), version = _specVersion$split2[0], canary = _specVersion$split2[1];
      var _version$split$map = version.split('.').map(Number), _version$split$map2 = _slicedToArray(_version$split$map, 3), major = _version$split$map2[0], minor = _version$split$map2[1], patch = _version$split$map2[2];
      var _axe$version$split = axe.version.split('-'), _axe$version$split2 = _slicedToArray(_axe$version$split, 2), axeVersion = _axe$version$split2[0], axeCanary = _axe$version$split2[1];
      var _axeVersion$split$map = axeVersion.split('.').map(Number), _axeVersion$split$map2 = _slicedToArray(_axeVersion$split$map, 3), axeMajor = _axeVersion$split$map2[0], axeMinor = _axeVersion$split$map2[1], axePatch = _axeVersion$split$map2[2];
      if (major !== axeMajor || axeMinor < minor || axeMinor === minor && axePatch < patch || major === axeMajor && minor === axeMinor && patch === axePatch && canary && canary !== axeCanary) {
        throw new Error('Configured version '.concat(specVersion, ' is not compatible with current axe version ').concat(axe.version));
      }
    }
    if (spec.reporter && (typeof spec.reporter === 'function' || reporters[spec.reporter])) {
      audit.reporter = spec.reporter;
    }
    if (spec.checks) {
      if (!Array.isArray(spec.checks)) {
        throw new TypeError('Checks property must be an array');
      }
      spec.checks.forEach(function(check) {
        if (!check.id) {
          throw new TypeError('Configured check '.concat(JSON.stringify(check), ' is invalid. Checks must be an object with at least an id property'));
        }
        audit.addCheck(check);
      });
    }
    var modifiedRules = [];
    if (spec.rules) {
      if (!Array.isArray(spec.rules)) {
        throw new TypeError('Rules property must be an array');
      }
      spec.rules.forEach(function(rule) {
        if (!rule.id) {
          throw new TypeError('Configured rule '.concat(JSON.stringify(rule), ' is invalid. Rules must be an object with at least an id property'));
        }
        modifiedRules.push(rule.id);
        audit.addRule(rule);
      });
    }
    if (spec.disableOtherRules) {
      audit.rules.forEach(function(rule) {
        if (modifiedRules.includes(rule.id) === false) {
          rule.enabled = false;
        }
      });
    }
    if (typeof spec.branding !== 'undefined') {
      audit.setBranding(spec.branding);
    } else {
      audit._constructHelpUrls();
    }
    if (spec.tagExclude) {
      audit.tagExclude = spec.tagExclude;
    }
    if (spec.locale) {
      audit.applyLocale(spec.locale);
    }
  }
  axe.configure = configureChecksRulesAndBranding;
  'use strict';
  axe.getRules = function(tags) {
    'use strict';
    tags = tags || [];
    var matchingRules = !tags.length ? axe._audit.rules : axe._audit.rules.filter(function(item) {
      return !!tags.filter(function(tag) {
        return item.tags.indexOf(tag) !== -1;
      }).length;
    });
    var ruleData = axe._audit.data.rules || {};
    return matchingRules.map(function(matchingRule) {
      var rd = ruleData[matchingRule.id] || {};
      return {
        ruleId: matchingRule.id,
        description: rd.description,
        help: rd.help,
        helpUrl: rd.helpUrl,
        tags: matchingRule.tags
      };
    });
  };
  'use strict';
  function runCommand(data, keepalive, callback) {
    'use strict';
    var resolve = callback;
    var reject = function reject(err) {
      if (err instanceof Error === false) {
        err = new Error(err);
      }
      callback(err);
    };
    var context = data && data.context || {};
    if (context.hasOwnProperty('include') && !context.include.length) {
      context.include = [ document ];
    }
    var options = data && data.options || {};
    switch (data.command) {
     case 'rules':
      return runRules(context, options, function(results, cleanup) {
        resolve(results);
        cleanup();
      }, reject);

     case 'cleanup-plugin':
      return cleanupPlugins(resolve, reject);

     default:
      if (axe._audit && axe._audit.commands && axe._audit.commands[data.command]) {
        return axe._audit.commands[data.command](data, callback);
      }
    }
  }
  axe._load = function(audit) {
    'use strict';
    axe.utils.respondable.subscribe('axe.ping', function(data, keepalive, respond) {
      respond({
        axe: true
      });
    });
    axe.utils.respondable.subscribe('axe.start', runCommand);
    axe._audit = new Audit(audit);
  };
  'use strict';
  var axe = axe || {};
  axe.plugins = {};
  function Plugin(spec) {
    'use strict';
    this._run = spec.run;
    this._collect = spec.collect;
    this._registry = {};
    spec.commands.forEach(function(command) {
      axe._audit.registerCommand(command);
    });
  }
  Plugin.prototype.run = function() {
    'use strict';
    return this._run.apply(this, arguments);
  };
  Plugin.prototype.collect = function() {
    'use strict';
    return this._collect.apply(this, arguments);
  };
  Plugin.prototype.cleanup = function(done) {
    'use strict';
    var q = axe.utils.queue();
    var that = this;
    Object.keys(this._registry).forEach(function(key) {
      q.defer(function(done) {
        that._registry[key].cleanup(done);
      });
    });
    q.then(function() {
      done();
    });
  };
  Plugin.prototype.add = function(impl) {
    'use strict';
    this._registry[impl.id] = impl;
  };
  axe.registerPlugin = function(plugin) {
    'use strict';
    axe.plugins[plugin.id] = new Plugin(plugin);
  };
  'use strict';
  var reporters = {};
  var defaultReporter;
  axe.getReporter = function(reporter) {
    'use strict';
    if (typeof reporter === 'string' && reporters[reporter]) {
      return reporters[reporter];
    }
    if (typeof reporter === 'function') {
      return reporter;
    }
    return defaultReporter;
  };
  axe.addReporter = function registerReporter(name, cb, isDefault) {
    'use strict';
    reporters[name] = cb;
    if (isDefault) {
      defaultReporter = cb;
    }
  };
  'use strict';
  function resetConfiguration() {
    'use strict';
    var audit = axe._audit;
    if (!audit) {
      throw new Error('No audit configured');
    }
    audit.resetRulesAndChecks();
  }
  axe.reset = resetConfiguration;
  'use strict';
  function cleanup() {
    axe._memoizedFns.forEach(function(fn) {
      return fn.clear();
    });
    axe._cache.clear();
    axe._tree = undefined;
    axe._selectorData = undefined;
  }
  function runRules(context, options, resolve, reject) {
    'use strict';
    try {
      context = new Context(context);
      axe._tree = context.flatTree;
      axe._selectorData = axe.utils.getSelectorData(context.flatTree);
    } catch (e) {
      cleanup();
      return reject(e);
    }
    var q = axe.utils.queue();
    var audit = axe._audit;
    if (options.performanceTimer) {
      axe.utils.performanceTimer.auditStart();
    }
    if (context.frames.length && options.iframes !== false) {
      q.defer(function(res, rej) {
        axe.utils.collectResultsFromFrames(context, options, 'rules', null, res, rej);
      });
    }
    var scrollState;
    q.defer(function(res, rej) {
      if (options.restoreScroll) {
        scrollState = axe.utils.getScrollState();
      }
      audit.run(context, options, res, rej);
    });
    q.then(function(data) {
      try {
        if (scrollState) {
          axe.utils.setScrollState(scrollState);
        }
        if (options.performanceTimer) {
          axe.utils.performanceTimer.auditEnd();
        }
        var results = axe.utils.mergeResults(data.map(function(results) {
          return {
            results: results
          };
        }));
        if (context.initiator) {
          results = audit.after(results, options);
          results.forEach(axe.utils.publishMetaData);
          results = results.map(axe.utils.finalizeRuleResult);
        }
        try {
          resolve(results, cleanup);
        } catch (e) {
          cleanup();
          axe.log(e);
        }
      } catch (e) {
        cleanup();
        reject(e);
      }
    })['catch'](function(e) {
      cleanup();
      reject(e);
    });
  }
  axe._runRules = runRules;
  'use strict';
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  axe.runVirtualRule = function(ruleId, vNode) {
    var options = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {};
    options.reporter = options.reporter || axe._audit.reporter || 'v1';
    axe._selectorData = {};
    if (vNode instanceof axe.AbstractVirtualNode === false) {
      vNode = new SerialVirtualNode(vNode);
    }
    var rule = axe._audit.rules.find(function(rule) {
      return rule.id === ruleId;
    });
    if (!rule) {
      throw new Error('unknown rule `' + ruleId + '`');
    }
    rule = Object.create(rule, {
      excludeHidden: {
        value: false
      }
    });
    var context = {
      include: [ vNode ]
    };
    var rawResults = rule.runSync(context, options);
    axe.utils.publishMetaData(rawResults);
    axe.utils.finalizeRuleResult(rawResults);
    var results = axe.utils.aggregateResult([ rawResults ]);
    results.violations.forEach(function(result) {
      return result.nodes.forEach(function(nodeResult) {
        nodeResult.failureSummary = helpers.failureSummary(nodeResult);
      });
    });
    return _extends({}, helpers.getEnvironmentData(), {}, results, {
      toolOptions: options
    });
  };
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  function isContext(potential) {
    'use strict';
    switch (true) {
     case typeof potential === 'string':
     case Array.isArray(potential):
     case Node && potential instanceof Node:
     case NodeList && potential instanceof NodeList:
      return true;

     case _typeof(potential) !== 'object':
      return false;

     case potential.include !== undefined:
     case potential.exclude !== undefined:
     case typeof potential.length === 'number':
      return true;

     default:
      return false;
    }
  }
  var noop = function noop() {};
  function normalizeRunParams(context, options, callback) {
    'use strict';
    var typeErr = new TypeError('axe.run arguments are invalid');
    if (!isContext(context)) {
      if (callback !== undefined) {
        throw typeErr;
      }
      callback = options;
      options = context;
      context = document;
    }
    if (_typeof(options) !== 'object') {
      if (callback !== undefined) {
        throw typeErr;
      }
      callback = options;
      options = {};
    }
    if (typeof callback !== 'function' && callback !== undefined) {
      throw typeErr;
    }
    return {
      context: context,
      options: options,
      callback: callback || noop
    };
  }
  axe.run = function(context, options, callback) {
    'use strict';
    if (!axe._audit) {
      throw new Error('No audit configured');
    }
    var args = normalizeRunParams(context, options, callback);
    context = args.context;
    options = args.options;
    callback = args.callback;
    options.reporter = options.reporter || axe._audit.reporter || 'v1';
    if (options.performanceTimer) {
      axe.utils.performanceTimer.start();
    }
    var p;
    var reject = noop;
    var resolve = noop;
    if (typeof Promise === 'function' && callback === noop) {
      p = new Promise(function(_resolve, _reject) {
        reject = _reject;
        resolve = _resolve;
      });
    }
    if (axe._running) {
      var err = 'Axe is already running. Use `await axe.run()` to wait ' + 'for the previous run to finish before starting a new run.';
      callback(err);
      reject(err);
      return p;
    }
    axe._running = true;
    axe._runRules(context, options, function(rawResults, cleanup) {
      var respond = function respond(results) {
        axe._running = false;
        cleanup();
        try {
          callback(null, results);
        } catch (e) {
          axe.log(e);
        }
        resolve(results);
      };
      if (options.performanceTimer) {
        axe.utils.performanceTimer.end();
      }
      try {
        var reporter = axe.getReporter(options.reporter);
        var results = reporter(rawResults, options, respond);
        if (results !== undefined) {
          respond(results);
        }
      } catch (err) {
        axe._running = false;
        cleanup();
        callback(err);
        reject(err);
      }
    }, function(err) {
      axe._running = false;
      callback(err);
      reject(err);
    });
    return p;
  };
  'use strict';
  helpers.failureSummary = function failureSummary(nodeData) {
    'use strict';
    var failingChecks = {};
    failingChecks.none = nodeData.none.concat(nodeData.all);
    failingChecks.any = nodeData.any;
    return Object.keys(failingChecks).map(function(key) {
      if (!failingChecks[key].length) {
        return;
      }
      var sum = axe._audit.data.failureSummaries[key];
      if (sum && typeof sum.failureMessage === 'function') {
        return sum.failureMessage(failingChecks[key].map(function(check) {
          return check.message || '';
        }));
      }
    }).filter(function(i) {
      return i !== undefined;
    }).join('\n\n');
  };
  'use strict';
  helpers.getEnvironmentData = function getEnvironmentData() {
    var win = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : window;
    var _win$screen = win.screen, screen = _win$screen === void 0 ? {} : _win$screen, _win$navigator = win.navigator, navigator = _win$navigator === void 0 ? {} : _win$navigator, _win$location = win.location, location = _win$location === void 0 ? {} : _win$location, innerHeight = win.innerHeight, innerWidth = win.innerWidth;
    var orientation = screen.msOrientation || screen.orientation || screen.mozOrientation || {};
    return {
      testEngine: {
        name: 'axe-core',
        version: axe.version
      },
      testRunner: {
        name: axe._audit.brand
      },
      testEnvironment: {
        userAgent: navigator.userAgent,
        windowWidth: innerWidth,
        windowHeight: innerHeight,
        orientationAngle: orientation.angle,
        orientationType: orientation.type
      },
      timestamp: new Date().toISOString(),
      url: location.href
    };
  };
  'use strict';
  helpers.incompleteFallbackMessage = function incompleteFallbackMessage() {
    'use strict';
    return typeof axe._audit.data.incompleteFallbackMessage === 'function' ? axe._audit.data.incompleteFallbackMessage() : axe._audit.data.incompleteFallbackMessage;
  };
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  function normalizeRelatedNodes(node, options) {
    'use strict';
    [ 'any', 'all', 'none' ].forEach(function(type) {
      if (!Array.isArray(node[type])) {
        return;
      }
      node[type].filter(function(checkRes) {
        return Array.isArray(checkRes.relatedNodes);
      }).forEach(function(checkRes) {
        checkRes.relatedNodes = checkRes.relatedNodes.map(function(relatedNode) {
          var res = {
            html: relatedNode.source
          };
          if (options.elementRef && !relatedNode.fromFrame) {
            res.element = relatedNode.element;
          }
          if (options.selectors !== false || relatedNode.fromFrame) {
            res.target = relatedNode.selector;
          }
          if (options.xpath) {
            res.xpath = relatedNode.xpath;
          }
          return res;
        });
      });
    });
  }
  var resultKeys = axe.constants.resultGroups;
  helpers.processAggregate = function(results, options) {
    var resultObject = axe.utils.aggregateResult(results);
    resultKeys.forEach(function(key) {
      if (options.resultTypes && !options.resultTypes.includes(key)) {
        (resultObject[key] || []).forEach(function(ruleResult) {
          if (Array.isArray(ruleResult.nodes) && ruleResult.nodes.length > 0) {
            ruleResult.nodes = [ ruleResult.nodes[0] ];
          }
        });
      }
      resultObject[key] = (resultObject[key] || []).map(function(ruleResult) {
        ruleResult = Object.assign({}, ruleResult);
        if (Array.isArray(ruleResult.nodes) && ruleResult.nodes.length > 0) {
          ruleResult.nodes = ruleResult.nodes.map(function(subResult) {
            if (_typeof(subResult.node) === 'object') {
              subResult.html = subResult.node.source;
              if (options.elementRef && !subResult.node.fromFrame) {
                subResult.element = subResult.node.element;
              }
              if (options.selectors !== false || subResult.node.fromFrame) {
                subResult.target = subResult.node.selector;
              }
              if (options.xpath) {
                subResult.xpath = subResult.node.xpath;
              }
            }
            delete subResult.result;
            delete subResult.node;
            normalizeRelatedNodes(subResult, options);
            return subResult;
          });
        }
        resultKeys.forEach(function(key) {
          return delete ruleResult[key];
        });
        delete ruleResult.pageLevel;
        delete ruleResult.result;
        return ruleResult;
      });
    });
    return resultObject;
  };
  'use strict';
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  axe.addReporter('na', function(results, options, callback) {
    'use strict';
    console.warn('"na" reporter will be deprecated in axe v4.0. Use the "v2" reporter instead.');
    if (typeof options === 'function') {
      callback = options;
      options = {};
    }
    var out = helpers.processAggregate(results, options);
    callback(_extends({}, helpers.getEnvironmentData(), {
      toolOptions: options,
      violations: out.violations,
      passes: out.passes,
      incomplete: out.incomplete,
      inapplicable: out.inapplicable
    }));
  });
  'use strict';
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  axe.addReporter('no-passes', function(results, options, callback) {
    'use strict';
    if (typeof options === 'function') {
      callback = options;
      options = {};
    }
    options.resultTypes = [ 'violations' ];
    var out = helpers.processAggregate(results, options);
    callback(_extends({}, helpers.getEnvironmentData(), {
      toolOptions: options,
      violations: out.violations
    }));
  });
  'use strict';
  axe.addReporter('rawEnv', function(results, options, callback) {
    if (typeof options === 'function') {
      callback = options;
      options = {};
    }
    function rawCallback(raw) {
      var env = helpers.getEnvironmentData();
      callback({
        raw: raw,
        env: env
      });
    }
    axe.getReporter('raw')(results, options, rawCallback);
  });
  'use strict';
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  axe.addReporter('raw', function(results, options, callback) {
    'use strict';
    if (typeof options === 'function') {
      callback = options;
      options = {};
    }
    if (!results || !Array.isArray(results)) {
      return callback(results);
    }
    var transformedResults = results.map(function(result) {
      var transformedResult = _extends({}, result);
      var types = [ 'passes', 'violations', 'incomplete', 'inapplicable' ];
      for (var _i = 0, _types = types; _i < _types.length; _i++) {
        var type = _types[_i];
        if (transformedResult[type] && Array.isArray(transformedResult[type])) {
          transformedResult[type] = transformedResult[type].map(function(typeResult) {
            return _extends({}, typeResult, {
              node: typeResult.node.toJSON()
            });
          });
        }
      }
      return transformedResult;
    });
    callback(transformedResults);
  });
  'use strict';
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  axe.addReporter('v1', function(results, options, callback) {
    'use strict';
    if (typeof options === 'function') {
      callback = options;
      options = {};
    }
    var out = helpers.processAggregate(results, options);
    var addFailureSummaries = function addFailureSummaries(result) {
      result.nodes.forEach(function(nodeResult) {
        nodeResult.failureSummary = helpers.failureSummary(nodeResult);
      });
    };
    out.incomplete.forEach(addFailureSummaries);
    out.violations.forEach(addFailureSummaries);
    callback(_extends({}, helpers.getEnvironmentData(), {
      toolOptions: options,
      violations: out.violations,
      passes: out.passes,
      incomplete: out.incomplete,
      inapplicable: out.inapplicable
    }));
  });
  'use strict';
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  axe.addReporter('v2', function(results, options, callback) {
    'use strict';
    if (typeof options === 'function') {
      callback = options;
      options = {};
    }
    var out = helpers.processAggregate(results, options);
    callback(_extends({}, helpers.getEnvironmentData(), {
      toolOptions: options,
      violations: out.violations,
      passes: out.passes,
      incomplete: out.incomplete,
      inapplicable: out.inapplicable
    }));
  }, true);
  'use strict';
  axe.utils.aggregate = function(map, values, initial) {
    values = values.slice();
    if (initial) {
      values.push(initial);
    }
    var sorting = values.map(function(val) {
      return map.indexOf(val);
    }).sort();
    return map[sorting.pop()];
  };
  'use strict';
  var _axe$constants = axe.constants, CANTTELL_PRIO = _axe$constants.CANTTELL_PRIO, FAIL_PRIO = _axe$constants.FAIL_PRIO;
  var checkMap = [];
  checkMap[axe.constants.PASS_PRIO] = true;
  checkMap[axe.constants.CANTTELL_PRIO] = null;
  checkMap[axe.constants.FAIL_PRIO] = false;
  var checkTypes = [ 'any', 'all', 'none' ];
  function anyAllNone(obj, functor) {
    return checkTypes.reduce(function(out, type) {
      out[type] = (obj[type] || []).map(function(val) {
        return functor(val, type);
      });
      return out;
    }, {});
  }
  axe.utils.aggregateChecks = function(nodeResOriginal) {
    var nodeResult = Object.assign({}, nodeResOriginal);
    anyAllNone(nodeResult, function(check, type) {
      var i = typeof check.result === 'undefined' ? -1 : checkMap.indexOf(check.result);
      check.priority = i !== -1 ? i : axe.constants.CANTTELL_PRIO;
      if (type === 'none') {
        if (check.priority === axe.constants.PASS_PRIO) {
          check.priority = axe.constants.FAIL_PRIO;
        } else if (check.priority === axe.constants.FAIL_PRIO) {
          check.priority = axe.constants.PASS_PRIO;
        }
      }
    });
    var priorities = {
      all: nodeResult.all.reduce(function(a, b) {
        return Math.max(a, b.priority);
      }, 0),
      none: nodeResult.none.reduce(function(a, b) {
        return Math.max(a, b.priority);
      }, 0),
      any: nodeResult.any.reduce(function(a, b) {
        return Math.min(a, b.priority);
      }, 4) % 4
    };
    nodeResult.priority = Math.max(priorities.all, priorities.none, priorities.any);
    var impacts = [];
    checkTypes.forEach(function(type) {
      nodeResult[type] = nodeResult[type].filter(function(check) {
        return check.priority === nodeResult.priority && check.priority === priorities[type];
      });
      nodeResult[type].forEach(function(check) {
        return impacts.push(check.impact);
      });
    });
    if ([ CANTTELL_PRIO, FAIL_PRIO ].includes(nodeResult.priority)) {
      nodeResult.impact = axe.utils.aggregate(axe.constants.impact, impacts);
    } else {
      nodeResult.impact = null;
    }
    anyAllNone(nodeResult, function(c) {
      delete c.result;
      delete c.priority;
    });
    nodeResult.result = axe.constants.results[nodeResult.priority];
    delete nodeResult.priority;
    return nodeResult;
  };
  'use strict';
  (function() {
    axe.utils.aggregateNodeResults = function(nodeResults) {
      var ruleResult = {};
      nodeResults = nodeResults.map(function(nodeResult) {
        if (nodeResult.any && nodeResult.all && nodeResult.none) {
          return axe.utils.aggregateChecks(nodeResult);
        } else if (Array.isArray(nodeResult.node)) {
          return axe.utils.finalizeRuleResult(nodeResult);
        } else {
          throw new TypeError('Invalid Result type');
        }
      });
      if (nodeResults && nodeResults.length) {
        var resultList = nodeResults.map(function(node) {
          return node.result;
        });
        ruleResult.result = axe.utils.aggregate(axe.constants.results, resultList, ruleResult.result);
      } else {
        ruleResult.result = 'inapplicable';
      }
      axe.constants.resultGroups.forEach(function(group) {
        return ruleResult[group] = [];
      });
      nodeResults.forEach(function(nodeResult) {
        var groupName = axe.constants.resultGroupMap[nodeResult.result];
        ruleResult[groupName].push(nodeResult);
      });
      var impactGroup = axe.constants.FAIL_GROUP;
      if (ruleResult[impactGroup].length === 0) {
        impactGroup = axe.constants.CANTTELL_GROUP;
      }
      if (ruleResult[impactGroup].length > 0) {
        var impactList = ruleResult[impactGroup].map(function(failure) {
          return failure.impact;
        });
        ruleResult.impact = axe.utils.aggregate(axe.constants.impact, impactList) || null;
      } else {
        ruleResult.impact = null;
      }
      return ruleResult;
    };
  })();
  'use strict';
  function copyToGroup(resultObject, subResult, group) {
    var resultCopy = Object.assign({}, subResult);
    resultCopy.nodes = (resultCopy[group] || []).concat();
    axe.constants.resultGroups.forEach(function(group) {
      delete resultCopy[group];
    });
    resultObject[group].push(resultCopy);
  }
  axe.utils.aggregateResult = function(results) {
    var resultObject = {};
    axe.constants.resultGroups.forEach(function(groupName) {
      return resultObject[groupName] = [];
    });
    results.forEach(function(subResult) {
      if (subResult.error) {
        copyToGroup(resultObject, subResult, axe.constants.CANTTELL_GROUP);
      } else if (subResult.result === axe.constants.NA) {
        copyToGroup(resultObject, subResult, axe.constants.NA_GROUP);
      } else {
        axe.constants.resultGroups.forEach(function(group) {
          if (Array.isArray(subResult[group]) && subResult[group].length > 0) {
            copyToGroup(resultObject, subResult, group);
          }
        });
      }
    });
    return resultObject;
  };
  'use strict';
  function areStylesSet(el, styles, stopAt) {
    'use strict';
    var styl = window.getComputedStyle(el, null);
    if (!styl) {
      return false;
    }
    for (var i = 0; i < styles.length; ++i) {
      var att = styles[i];
      if (styl.getPropertyValue(att.property) === att.value) {
        return true;
      }
    }
    if (!el.parentNode || el.nodeName.toUpperCase() === stopAt.toUpperCase()) {
      return false;
    }
    return areStylesSet(el.parentNode, styles, stopAt);
  }
  axe.utils.areStylesSet = areStylesSet;
  'use strict';
  axe.utils.assert = function assert(bool, message) {
    if (!bool) {
      throw new Error(message);
    }
  };
  'use strict';
  axe.utils.checkHelper = function checkHelper(checkResult, options, resolve, reject) {
    'use strict';
    return {
      isAsync: false,
      async: function async() {
        this.isAsync = true;
        return function(result) {
          if (result instanceof Error === false) {
            checkResult.result = result;
            resolve(checkResult);
          } else {
            reject(result);
          }
        };
      },
      data: function data(_data) {
        checkResult.data = _data;
      },
      relatedNodes: function relatedNodes(nodes) {
        nodes = nodes instanceof Node ? [ nodes ] : axe.utils.toArray(nodes);
        checkResult.relatedNodes = nodes.map(function(element) {
          return new axe.utils.DqElement(element, options);
        });
      }
    };
  };
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  axe.utils.clone = function(obj) {
    'use strict';
    var index, length, out = obj;
    if (obj !== null && _typeof(obj) === 'object') {
      if (Array.isArray(obj)) {
        out = [];
        for (index = 0, length = obj.length; index < length; index++) {
          out[index] = axe.utils.clone(obj[index]);
        }
      } else {
        out = {};
        for (index in obj) {
          out[index] = axe.utils.clone(obj[index]);
        }
      }
    }
    return out;
  };
  'use strict';
  function err(message, node) {
    'use strict';
    var selector;
    if (axe._tree) {
      selector = axe.utils.getSelector(node);
    }
    return new Error(message + ': ' + (selector || node));
  }
  axe.utils.sendCommandToFrame = function(node, parameters, resolve, reject) {
    'use strict';
    var win = node.contentWindow;
    if (!win) {
      axe.log('Frame does not have a content window', node);
      resolve(null);
      return;
    }
    var timeout = setTimeout(function() {
      timeout = setTimeout(function() {
        if (!parameters.debug) {
          resolve(null);
        } else {
          reject(err('No response from frame', node));
        }
      }, 0);
    }, 500);
    axe.utils.respondable(win, 'axe.ping', null, undefined, function() {
      clearTimeout(timeout);
      var frameWaitTime = parameters.options && parameters.options.frameWaitTime || 6e4;
      timeout = setTimeout(function collectResultFramesTimeout() {
        reject(err('Axe in frame timed out', node));
      }, frameWaitTime);
      axe.utils.respondable(win, 'axe.start', parameters, undefined, function(data) {
        clearTimeout(timeout);
        if (data instanceof Error === false) {
          resolve(data);
        } else {
          reject(data);
        }
      });
    });
  };
  function collectResultsFromFrames(context, options, command, parameter, resolve, reject) {
    'use strict';
    var q = axe.utils.queue();
    var frames = context.frames;
    frames.forEach(function(frame) {
      var params = {
        options: options,
        command: command,
        parameter: parameter,
        context: {
          initiator: false,
          page: context.page,
          include: frame.include || [],
          exclude: frame.exclude || []
        }
      };
      q.defer(function(res, rej) {
        var node = frame.node;
        axe.utils.sendCommandToFrame(node, params, function(data) {
          if (data) {
            return res({
              results: data,
              frameElement: node,
              frame: axe.utils.getSelector(node)
            });
          }
          res(null);
        }, rej);
      });
    });
    q.then(function(data) {
      resolve(axe.utils.mergeResults(data, options));
    })['catch'](reject);
  }
  axe.utils.collectResultsFromFrames = collectResultsFromFrames;
  'use strict';
  axe.utils.contains = function(vNode, otherVNode) {
    'use strict';
    function containsShadowChild(vNode, otherVNode) {
      if (vNode.shadowId === otherVNode.shadowId) {
        return true;
      }
      return !!vNode.children.find(function(child) {
        return containsShadowChild(child, otherVNode);
      });
    }
    if (vNode.shadowId || otherVNode.shadowId) {
      return containsShadowChild(vNode, otherVNode);
    }
    if (vNode.actualNode) {
      if (typeof vNode.actualNode.contains === 'function') {
        return vNode.actualNode.contains(otherVNode.actualNode);
      }
      return !!(vNode.actualNode.compareDocumentPosition(otherVNode.actualNode) & 16);
    } else {
      do {
        if (otherVNode === vNode) {
          return true;
        }
      } while (otherVNode = otherVNode && otherVNode.parent);
    }
    return false;
  };
  'use strict';
  (function(axe) {
    var parser = new axe.imports.CssSelectorParser();
    parser.registerSelectorPseudos('not');
    parser.registerNestingOperators('>');
    parser.registerAttrEqualityMods('^', '$', '*');
    axe.utils.cssParser = parser;
  })(axe);
  'use strict';
  function truncate(str, maxLength) {
    maxLength = maxLength || 300;
    if (str.length > maxLength) {
      var index = str.indexOf('>');
      str = str.substring(0, index + 1);
    }
    return str;
  }
  function getSource(element) {
    var source = element.outerHTML;
    if (!source && typeof XMLSerializer === 'function') {
      source = new XMLSerializer().serializeToString(element);
    }
    return truncate(source || '');
  }
  function DqElement(element, options, spec) {
    this._fromFrame = !!spec;
    this.spec = spec || {};
    if (options && options.absolutePaths) {
      this._options = {
        toRoot: true
      };
    }
    this.source = this.spec.source !== undefined ? this.spec.source : getSource(element);
    this._element = element;
  }
  DqElement.prototype = {
    get selector() {
      return this.spec.selector || [ axe.utils.getSelector(this.element, this._options) ];
    },
    get xpath() {
      return this.spec.xpath || [ axe.utils.getXpath(this.element) ];
    },
    get element() {
      return this._element;
    },
    get fromFrame() {
      return this._fromFrame;
    },
    toJSON: function toJSON() {
      'use strict';
      return {
        selector: this.selector,
        source: this.source,
        xpath: this.xpath
      };
    }
  };
  DqElement.fromFrame = function(node, options, frame) {
    node.selector.unshift(frame.selector);
    node.xpath.unshift(frame.xpath);
    return new axe.utils.DqElement(frame.element, options, node);
  };
  axe.utils.DqElement = DqElement;
  'use strict';
  axe.utils.matchesSelector = function() {
    'use strict';
    var method;
    function getMethod(node) {
      var index, candidate, candidates = [ 'matches', 'matchesSelector', 'mozMatchesSelector', 'webkitMatchesSelector', 'msMatchesSelector' ], length = candidates.length;
      for (index = 0; index < length; index++) {
        candidate = candidates[index];
        if (node[candidate]) {
          return candidate;
        }
      }
    }
    return function(node, selector) {
      if (!method || !node[method]) {
        method = getMethod(node);
      }
      if (node[method]) {
        return node[method](selector);
      }
      return false;
    };
  }();
  'use strict';
  axe.utils.escapeSelector = function(value) {
    'use strict';
    var string = String(value);
    var length = string.length;
    var index = -1;
    var codeUnit;
    var result = '';
    var firstCodeUnit = string.charCodeAt(0);
    while (++index < length) {
      codeUnit = string.charCodeAt(index);
      if (codeUnit == 0) {
        result += '\ufffd';
        continue;
      }
      if (codeUnit >= 1 && codeUnit <= 31 || codeUnit == 127 || index == 0 && codeUnit >= 48 && codeUnit <= 57 || index == 1 && codeUnit >= 48 && codeUnit <= 57 && firstCodeUnit == 45) {
        result += '\\' + codeUnit.toString(16) + ' ';
        continue;
      }
      if (index == 0 && length == 1 && codeUnit == 45) {
        result += '\\' + string.charAt(index);
        continue;
      }
      if (codeUnit >= 128 || codeUnit == 45 || codeUnit == 95 || codeUnit >= 48 && codeUnit <= 57 || codeUnit >= 65 && codeUnit <= 90 || codeUnit >= 97 && codeUnit <= 122) {
        result += string.charAt(index);
        continue;
      }
      result += '\\' + string.charAt(index);
    }
    return result;
  };
  'use strict';
  axe.utils.extendMetaData = function(to, from) {
    Object.assign(to, from);
    Object.keys(from).filter(function(prop) {
      return typeof from[prop] === 'function';
    }).forEach(function(prop) {
      to[prop] = null;
      try {
        to[prop] = from[prop](to);
      } catch (e) {}
    });
  };
  'use strict';
  axe.utils.finalizeRuleResult = function(ruleResult) {
    Object.assign(ruleResult, axe.utils.aggregateNodeResults(ruleResult.nodes));
    delete ruleResult.nodes;
    return ruleResult;
  };
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  axe.utils.findBy = function(array, key, value) {
    if (Array.isArray(array)) {
      return array.find(function(obj) {
        return _typeof(obj) === 'object' && obj[key] === value;
      });
    }
  };
  'use strict';
  var axe = axe || {
    utils: {}
  };
  function getSlotChildren(node) {
    var retVal = [];
    node = node.firstChild;
    while (node) {
      retVal.push(node);
      node = node.nextSibling;
    }
    return retVal;
  }
  function flattenTree(node, shadowId, parent) {
    var retVal, realArray, nodeName;
    function reduceShadowDOM(res, child, parent) {
      var replacements = flattenTree(child, shadowId, parent);
      if (replacements) {
        res = res.concat(replacements);
      }
      return res;
    }
    if (node.documentElement) {
      node = node.documentElement;
    }
    nodeName = node.nodeName.toLowerCase();
    if (axe.utils.isShadowRoot(node)) {
      retVal = new VirtualNode(node, parent, shadowId);
      shadowId = 'a' + Math.random().toString().substring(2);
      realArray = Array.from(node.shadowRoot.childNodes);
      retVal.children = realArray.reduce(function(res, child) {
        return reduceShadowDOM(res, child, retVal);
      }, []);
      return [ retVal ];
    } else {
      if (nodeName === 'content' && typeof node.getDistributedNodes === 'function') {
        realArray = Array.from(node.getDistributedNodes());
        return realArray.reduce(function(res, child) {
          return reduceShadowDOM(res, child, parent);
        }, []);
      } else if (nodeName === 'slot' && typeof node.assignedNodes === 'function') {
        realArray = Array.from(node.assignedNodes());
        if (!realArray.length) {
          realArray = getSlotChildren(node);
        }
        var styl = window.getComputedStyle(node);
        if (false && styl.display !== 'contents') {
          retVal = new VirtualNode(node, parent, shadowId);
          retVal.children = realArray.reduce(function(res, child) {
            return reduceShadowDOM(res, child, retVal);
          }, []);
          return [ retVal ];
        } else {
          return realArray.reduce(function(res, child) {
            return reduceShadowDOM(res, child, parent);
          }, []);
        }
      } else {
        if (node.nodeType === 1) {
          retVal = new VirtualNode(node, parent, shadowId);
          realArray = Array.from(node.childNodes);
          retVal.children = realArray.reduce(function(res, child) {
            return reduceShadowDOM(res, child, retVal);
          }, []);
          return [ retVal ];
        } else if (node.nodeType === 3) {
          return [ new VirtualNode(node, parent) ];
        }
        return undefined;
      }
    }
  }
  axe.utils.getFlattenedTree = function(node, shadowId) {
    axe._cache.set('nodeMap', new WeakMap());
    return flattenTree(node, shadowId);
  };
  axe.utils.getNodeFromTree = function(vNode, node) {
    var el = node || vNode;
    return axe._cache.get('nodeMap') ? axe._cache.get('nodeMap').get(el) : null;
  };
  'use strict';
  axe.utils.getAllChecks = function getAllChecks(object) {
    'use strict';
    var result = [];
    return result.concat(object.any || []).concat(object.all || []).concat(object.none || []);
  };
  'use strict';
  axe.utils.getBaseLang = function getBaseLang(lang) {
    if (!lang) {
      return '';
    }
    return lang.trim().split('-')[0].toLowerCase();
  };
  'use strict';
  axe.utils.getCheckMessage = function getCheckMessage(checkId, type, data) {
    var check = axe._audit.data.checks[checkId];
    if (!check) {
      throw new Error('Cannot get message for unknown check: '.concat(checkId, '.'));
    }
    if (!check.messages[type]) {
      throw new Error('Check "'.concat(checkId, '"" does not have a "').concat(type, '" message.'));
    }
    return axe.utils.processMessage(check.messages[type], data);
  };
  'use strict';
  axe.utils.getCheckOption = function(check, ruleID, options) {
    var ruleCheckOption = ((options.rules && options.rules[ruleID] || {}).checks || {})[check.id];
    var checkOption = (options.checks || {})[check.id];
    var enabled = check.enabled;
    var opts = check.options;
    if (checkOption) {
      if (checkOption.hasOwnProperty('enabled')) {
        enabled = checkOption.enabled;
      }
      if (checkOption.hasOwnProperty('options')) {
        opts = checkOption.options;
      }
    }
    if (ruleCheckOption) {
      if (ruleCheckOption.hasOwnProperty('enabled')) {
        enabled = ruleCheckOption.enabled;
      }
      if (ruleCheckOption.hasOwnProperty('options')) {
        opts = ruleCheckOption.options;
      }
    }
    return {
      enabled: enabled,
      options: opts,
      absolutePaths: options.absolutePaths
    };
  };
  'use strict';
  function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _nonIterableRest();
  }
  function _nonIterableRest() {
    throw new TypeError('Invalid attempt to destructure non-iterable instance');
  }
  function _iterableToArrayLimit(arr, i) {
    if (!(Symbol.iterator in Object(arr) || Object.prototype.toString.call(arr) === '[object Arguments]')) {
      return;
    }
    var _arr = [];
    var _n = true;
    var _d = false;
    var _e = undefined;
    try {
      for (var _i = arr[Symbol.iterator](), _s; !(_n = (_s = _i.next()).done); _n = true) {
        _arr.push(_s.value);
        if (i && _arr.length === i) {
          break;
        }
      }
    } catch (err) {
      _d = true;
      _e = err;
    } finally {
      try {
        if (!_n && _i['return'] != null) {
          _i['return']();
        }
      } finally {
        if (_d) {
          throw _e;
        }
      }
    }
    return _arr;
  }
  function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) {
      return arr;
    }
  }
  function isMostlyNumbers() {
    var str = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : '';
    return str.length !== 0 && (str.match(/[0-9]/g) || '').length >= str.length / 2;
  }
  function splitString(str, splitIndex) {
    return [ str.substring(0, splitIndex), str.substring(splitIndex) ];
  }
  function trimRight(str) {
    return str.replace(/\s+$/, '');
  }
  function uriParser(url) {
    var original = url;
    var protocol = '', domain = '', port = '', path = '', query = '', hash = '';
    if (url.includes('#')) {
      var _splitString = splitString(url, url.indexOf('#'));
      var _splitString2 = _slicedToArray(_splitString, 2);
      url = _splitString2[0];
      hash = _splitString2[1];
    }
    if (url.includes('?')) {
      var _splitString3 = splitString(url, url.indexOf('?'));
      var _splitString4 = _slicedToArray(_splitString3, 2);
      url = _splitString4[0];
      query = _splitString4[1];
    }
    if (url.includes('://')) {
      var _url$split = url.split('://');
      var _url$split2 = _slicedToArray(_url$split, 2);
      protocol = _url$split2[0];
      url = _url$split2[1];
      var _splitString5 = splitString(url, url.indexOf('/'));
      var _splitString6 = _slicedToArray(_splitString5, 2);
      domain = _splitString6[0];
      url = _splitString6[1];
    } else if (url.substr(0, 2) === '//') {
      url = url.substr(2);
      var _splitString7 = splitString(url, url.indexOf('/'));
      var _splitString8 = _slicedToArray(_splitString7, 2);
      domain = _splitString8[0];
      url = _splitString8[1];
    }
    if (domain.substr(0, 4) === 'www.') {
      domain = domain.substr(4);
    }
    if (domain && domain.includes(':')) {
      var _splitString9 = splitString(domain, domain.indexOf(':'));
      var _splitString10 = _slicedToArray(_splitString9, 2);
      domain = _splitString10[0];
      port = _splitString10[1];
    }
    path = url;
    return {
      original: original,
      protocol: protocol,
      domain: domain,
      port: port,
      path: path,
      query: query,
      hash: hash
    };
  }
  axe.utils.getFriendlyUriEnd = function getFriendlyUriEnd() {
    var uri = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : '';
    var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
    if (uri.length <= 1 || uri.substr(0, 5) === 'data:' || uri.substr(0, 11) === 'javascript:' || uri.includes('?')) {
      return;
    }
    var currentDomain = options.currentDomain, _options$maxLength = options.maxLength, maxLength = _options$maxLength === void 0 ? 25 : _options$maxLength;
    var _uriParser = uriParser(uri), path = _uriParser.path, domain = _uriParser.domain, hash = _uriParser.hash;
    var pathEnd = path.substr(path.substr(0, path.length - 2).lastIndexOf('/') + 1);
    if (hash) {
      if (pathEnd && (pathEnd + hash).length <= maxLength) {
        return trimRight(pathEnd + hash);
      } else if (pathEnd.length < 2 && hash.length > 2 && hash.length <= maxLength) {
        return trimRight(hash);
      } else {
        return;
      }
    } else if (domain && domain.length < maxLength && path.length <= 1) {
      return trimRight(domain + path);
    }
    if (path === '/' + pathEnd && domain && currentDomain && domain !== currentDomain && (domain + path).length <= maxLength) {
      return trimRight(domain + path);
    }
    var lastDotIndex = pathEnd.lastIndexOf('.');
    if ((lastDotIndex === -1 || lastDotIndex > 1) && (lastDotIndex !== -1 || pathEnd.length > 2) && pathEnd.length <= maxLength && !pathEnd.match(/index(\.[a-zA-Z]{2-4})?/) && !isMostlyNumbers(pathEnd)) {
      return trimRight(pathEnd);
    }
  };
  'use strict';
  axe.utils.getNodeAttributes = function getNodeAttributes(node) {
    if (node.attributes instanceof window.NamedNodeMap) {
      return node.attributes;
    }
    return node.cloneNode(false).attributes;
  };
  'use strict';
  axe.utils.getRootNode = function getRootNode(node) {
    var doc = node.getRootNode && node.getRootNode() || document;
    if (doc === node) {
      doc = document;
    }
    return doc;
  };
  'use strict';
  axe.utils.getScroll = function getScroll(elm) {
    var buffer = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 0;
    var overflowX = elm.scrollWidth > elm.clientWidth + buffer;
    var overflowY = elm.scrollHeight > elm.clientHeight + buffer;
    if (!(overflowX || overflowY)) {
      return;
    }
    var style = window.getComputedStyle(elm);
    var overflowXStyle = style.getPropertyValue('overflow-x');
    var overflowYStyle = style.getPropertyValue('overflow-y');
    var scrollableX = overflowXStyle !== 'visible' && overflowXStyle !== 'hidden';
    var scrollableY = overflowYStyle !== 'visible' && overflowYStyle !== 'hidden';
    if (overflowX && scrollableX || overflowY && scrollableY) {
      return {
        elm: elm,
        top: elm.scrollTop,
        left: elm.scrollLeft
      };
    }
  };
  'use strict';
  var escapeSelector = axe.utils.escapeSelector;
  var isXHTML;
  var ignoredAttributes = [ 'class', 'style', 'id', 'selected', 'checked', 'disabled', 'tabindex', 'aria-checked', 'aria-selected', 'aria-invalid', 'aria-activedescendant', 'aria-busy', 'aria-disabled', 'aria-expanded', 'aria-grabbed', 'aria-pressed', 'aria-valuenow' ];
  var MAXATTRIBUTELENGTH = 31;
  function getAttributeNameValue(node, at) {
    var name = at.name;
    var atnv;
    if (name.indexOf('href') !== -1 || name.indexOf('src') !== -1) {
      var friendly = axe.utils.getFriendlyUriEnd(node.getAttribute(name));
      if (friendly) {
        var value = encodeURI(friendly);
        if (value) {
          atnv = escapeSelector(at.name) + '$="' + escapeSelector(value) + '"';
        } else {
          return;
        }
      } else {
        atnv = escapeSelector(at.name) + '="' + escapeSelector(node.getAttribute(name)) + '"';
      }
    } else {
      atnv = escapeSelector(name) + '="' + escapeSelector(at.value) + '"';
    }
    return atnv;
  }
  function countSort(a, b) {
    return a.count < b.count ? -1 : a.count === b.count ? 0 : 1;
  }
  function filterAttributes(at) {
    return !ignoredAttributes.includes(at.name) && at.name.indexOf(':') === -1 && (!at.value || at.value.length < MAXATTRIBUTELENGTH);
  }
  axe.utils.getSelectorData = function(domTree) {
    var data = {
      classes: {},
      tags: {},
      attributes: {}
    };
    domTree = Array.isArray(domTree) ? domTree : [ domTree ];
    var currentLevel = domTree.slice();
    var stack = [];
    var _loop = function _loop() {
      var current = currentLevel.pop();
      var node = current.actualNode;
      if (!!node.querySelectorAll) {
        var tag = node.nodeName;
        if (data.tags[tag]) {
          data.tags[tag]++;
        } else {
          data.tags[tag] = 1;
        }
        if (node.classList) {
          Array.from(node.classList).forEach(function(cl) {
            var ind = escapeSelector(cl);
            if (data.classes[ind]) {
              data.classes[ind]++;
            } else {
              data.classes[ind] = 1;
            }
          });
        }
        if (node.hasAttributes()) {
          Array.from(axe.utils.getNodeAttributes(node)).filter(filterAttributes).forEach(function(at) {
            var atnv = getAttributeNameValue(node, at);
            if (atnv) {
              if (data.attributes[atnv]) {
                data.attributes[atnv]++;
              } else {
                data.attributes[atnv] = 1;
              }
            }
          });
        }
      }
      if (current.children.length) {
        stack.push(currentLevel);
        currentLevel = current.children.slice();
      }
      while (!currentLevel.length && stack.length) {
        currentLevel = stack.pop();
      }
    };
    while (currentLevel.length) {
      _loop();
    }
    return data;
  };
  function uncommonClasses(node, selectorData) {
    var retVal = [];
    var classData = selectorData.classes;
    var tagData = selectorData.tags;
    if (node.classList) {
      Array.from(node.classList).forEach(function(cl) {
        var ind = escapeSelector(cl);
        if (classData[ind] < tagData[node.nodeName]) {
          retVal.push({
            name: ind,
            count: classData[ind],
            species: 'class'
          });
        }
      });
    }
    return retVal.sort(countSort);
  }
  function getNthChildString(elm, selector) {
    var siblings = elm.parentNode && Array.from(elm.parentNode.children || '') || [];
    var hasMatchingSiblings = siblings.find(function(sibling) {
      return sibling !== elm && axe.utils.matchesSelector(sibling, selector);
    });
    if (hasMatchingSiblings) {
      var nthChild = 1 + siblings.indexOf(elm);
      return ':nth-child(' + nthChild + ')';
    } else {
      return '';
    }
  }
  function getElmId(elm) {
    if (!elm.getAttribute('id')) {
      return;
    }
    var doc = elm.getRootNode && elm.getRootNode() || document;
    var id = '#' + escapeSelector(elm.getAttribute('id') || '');
    if (!id.match(/player_uid_/) && doc.querySelectorAll(id).length === 1) {
      return id;
    }
  }
  function getBaseSelector(elm) {
    if (typeof isXHTML === 'undefined') {
      isXHTML = axe.utils.isXHTML(document);
    }
    return escapeSelector(isXHTML ? elm.localName : elm.nodeName.toLowerCase());
  }
  function uncommonAttributes(node, selectorData) {
    var retVal = [];
    var attData = selectorData.attributes;
    var tagData = selectorData.tags;
    if (node.hasAttributes()) {
      Array.from(axe.utils.getNodeAttributes(node)).filter(filterAttributes).forEach(function(at) {
        var atnv = getAttributeNameValue(node, at);
        if (atnv && attData[atnv] < tagData[node.nodeName]) {
          retVal.push({
            name: atnv,
            count: attData[atnv],
            species: 'attribute'
          });
        }
      });
    }
    return retVal.sort(countSort);
  }
  function getThreeLeastCommonFeatures(elm, selectorData) {
    var selector = '';
    var features;
    var clss = uncommonClasses(elm, selectorData);
    var atts = uncommonAttributes(elm, selectorData);
    if (clss.length && clss[0].count === 1) {
      features = [ clss[0] ];
    } else if (atts.length && atts[0].count === 1) {
      features = [ atts[0] ];
      selector = getBaseSelector(elm);
    } else {
      features = clss.concat(atts);
      features.sort(countSort);
      features = features.slice(0, 3);
      if (!features.some(function(feat) {
        return feat.species === 'class';
      })) {
        selector = getBaseSelector(elm);
      } else {
        features.sort(function(a, b) {
          return a.species !== b.species && a.species === 'class' ? -1 : a.species === b.species ? 0 : 1;
        });
      }
    }
    return selector += features.reduce(function(val, feat) {
      switch (feat.species) {
       case 'class':
        return val + '.' + feat.name;

       case 'attribute':
        return val + '[' + feat.name + ']';
      }
      return val;
    }, '');
  }
  function generateSelector(elm, options, doc) {
    if (!axe._selectorData) {
      throw new Error('Expect axe._selectorData to be set up');
    }
    var _options$toRoot = options.toRoot, toRoot = _options$toRoot === void 0 ? false : _options$toRoot;
    var selector;
    var similar;
    do {
      var features = getElmId(elm);
      if (!features) {
        features = getThreeLeastCommonFeatures(elm, axe._selectorData);
        features += getNthChildString(elm, features);
      }
      if (selector) {
        selector = features + ' > ' + selector;
      } else {
        selector = features;
      }
      if (!similar) {
        similar = Array.from(doc.querySelectorAll(selector));
      } else {
        similar = similar.filter(function(item) {
          return axe.utils.matchesSelector(item, selector);
        });
      }
      elm = elm.parentElement;
    } while ((similar.length > 1 || toRoot) && elm && elm.nodeType !== 11);
    if (similar.length === 1) {
      return selector;
    } else if (selector.indexOf(' > ') !== -1) {
      return ':root' + selector.substring(selector.indexOf(' > '));
    }
    return ':root';
  }
  axe.utils.getSelector = function createUniqueSelector(elm) {
    var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
    if (!elm) {
      return '';
    }
    var doc = elm.getRootNode && elm.getRootNode() || document;
    if (doc.nodeType === 11) {
      var stack = [];
      while (doc.nodeType === 11) {
        if (!doc.host) {
          return '';
        }
        stack.push({
          elm: elm,
          doc: doc
        });
        elm = doc.host;
        doc = elm.getRootNode();
      }
      stack.push({
        elm: elm,
        doc: doc
      });
      return stack.reverse().map(function(comp) {
        return generateSelector(comp.elm, options, comp.doc);
      });
    } else {
      return generateSelector(elm, options, doc);
    }
  };
  'use strict';
  axe.utils.getStyleSheetFactory = function getStyleSheetFactory(dynamicDoc) {
    if (!dynamicDoc) {
      throw new Error('axe.utils.getStyleSheetFactory should be invoked with an argument');
    }
    return function(options) {
      var data = options.data, _options$isCrossOrigi = options.isCrossOrigin, isCrossOrigin = _options$isCrossOrigi === void 0 ? false : _options$isCrossOrigi, shadowId = options.shadowId, root = options.root, priority = options.priority, _options$isLink = options.isLink, isLink = _options$isLink === void 0 ? false : _options$isLink;
      var style = dynamicDoc.createElement('style');
      if (isLink) {
        var text = dynamicDoc.createTextNode('@import "'.concat(data.href, '"'));
        style.appendChild(text);
      } else {
        style.appendChild(dynamicDoc.createTextNode(data));
      }
      dynamicDoc.head.appendChild(style);
      return {
        sheet: style.sheet,
        isCrossOrigin: isCrossOrigin,
        shadowId: shadowId,
        root: root,
        priority: priority
      };
    };
  };
  'use strict';
  function getXPathArray(node, path) {
    var sibling, count;
    if (!node) {
      return [];
    }
    if (!path && node.nodeType === 9) {
      path = [ {
        str: 'html'
      } ];
      return path;
    }
    path = path || [];
    if (node.parentNode && node.parentNode !== node) {
      path = getXPathArray(node.parentNode, path);
    }
    if (node.previousSibling) {
      count = 1;
      sibling = node.previousSibling;
      do {
        if (sibling.nodeType === 1 && sibling.nodeName === node.nodeName) {
          count++;
        }
        sibling = sibling.previousSibling;
      } while (sibling);
      if (count === 1) {
        count = null;
      }
    } else if (node.nextSibling) {
      sibling = node.nextSibling;
      do {
        if (sibling.nodeType === 1 && sibling.nodeName === node.nodeName) {
          count = 1;
          sibling = null;
        } else {
          count = null;
          sibling = sibling.previousSibling;
        }
      } while (sibling);
    }
    if (node.nodeType === 1) {
      var element = {};
      element.str = node.nodeName.toLowerCase();
      var id = node.getAttribute && axe.utils.escapeSelector(node.getAttribute('id'));
      if (id && node.ownerDocument.querySelectorAll('#' + id).length === 1) {
        element.id = node.getAttribute('id');
      }
      if (count > 1) {
        element.count = count;
      }
      path.push(element);
    }
    return path;
  }
  function xpathToString(xpathArray) {
    return xpathArray.reduce(function(str, elm) {
      if (elm.id) {
        return '/'.concat(elm.str, '[@id=\'').concat(elm.id, '\']');
      } else {
        return str + '/'.concat(elm.str) + (elm.count > 0 ? '['.concat(elm.count, ']') : '');
      }
    }, '');
  }
  axe.utils.getXpath = function getXpath(node) {
    var xpathArray = getXPathArray(node);
    return xpathToString(xpathArray);
  };
  'use strict';
  var styleSheet;
  function injectStyle(style) {
    'use strict';
    if (styleSheet && styleSheet.parentNode) {
      if (styleSheet.styleSheet === undefined) {
        styleSheet.appendChild(document.createTextNode(style));
      } else {
        styleSheet.styleSheet.cssText += style;
      }
      return styleSheet;
    }
    if (!style) {
      return;
    }
    var head = document.head || document.getElementsByTagName('head')[0];
    styleSheet = document.createElement('style');
    styleSheet.type = 'text/css';
    if (styleSheet.styleSheet === undefined) {
      styleSheet.appendChild(document.createTextNode(style));
    } else {
      styleSheet.styleSheet.cssText = style;
    }
    head.appendChild(styleSheet);
    return styleSheet;
  }
  axe.utils.injectStyle = injectStyle;
  'use strict';
  axe.utils.isHidden = function isHidden(el, recursed) {
    'use strict';
    var node = axe.utils.getNodeFromTree(el);
    if (el.nodeType === 9) {
      return false;
    }
    if (el.nodeType === 11) {
      el = el.host;
    }
    if (node && node._isHidden !== null) {
      return node._isHidden;
    }
    var style = window.getComputedStyle(el, null);
    if (!style || !el.parentNode || style.getPropertyValue('display') === 'none' || !recursed && style.getPropertyValue('visibility') === 'hidden' || el.getAttribute('aria-hidden') === 'true') {
      return true;
    }
    var parent = el.assignedSlot ? el.assignedSlot : el.parentNode;
    var isHidden = axe.utils.isHidden(parent, true);
    if (node) {
      node._isHidden = isHidden;
    }
    return isHidden;
  };
  'use strict';
  var htmlTags = [ 'a', 'abbr', 'address', 'area', 'article', 'aside', 'audio', 'b', 'base', 'bdi', 'bdo', 'blockquote', 'body', 'br', 'button', 'canvas', 'caption', 'cite', 'code', 'col', 'colgroup', 'data', 'datalist', 'dd', 'del', 'details', 'dfn', 'dialog', 'div', 'dl', 'dt', 'em', 'embed', 'fieldset', 'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'head', 'header', 'hgroup', 'hr', 'html', 'i', 'iframe', 'img', 'input', 'ins', 'kbd', 'keygen', 'label', 'legend', 'li', 'link', 'main', 'map', 'mark', 'math', 'menu', 'menuitem', 'meta', 'meter', 'nav', 'noscript', 'object', 'ol', 'optgroup', 'option', 'output', 'p', 'param', 'picture', 'pre', 'progress', 'q', 'rb', 'rp', 'rt', 'rtc', 'ruby', 's', 'samp', 'script', 'section', 'select', 'slot', 'small', 'source', 'span', 'strong', 'style', 'sub', 'summary', 'sup', 'svg', 'table', 'tbody', 'td', 'template', 'textarea', 'tfoot', 'th', 'thead', 'time', 'title', 'tr', 'track', 'u', 'ul', 'var', 'video', 'wbr' ];
  axe.utils.isHtmlElement = function isHtmlElement(node) {
    if (node.namespaceURI === 'http://www.w3.org/2000/svg') {
      return false;
    }
    return htmlTags.includes(node.nodeName.toLowerCase());
  };
  'use strict';
  var possibleShadowRoots = [ 'article', 'aside', 'blockquote', 'body', 'div', 'footer', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'main', 'nav', 'p', 'section', 'span' ];
  axe.utils.isShadowRoot = function isShadowRoot(node) {
    if (node.shadowRoot) {
      var nodeName = node.nodeName.toLowerCase();
      if (possibleShadowRoots.includes(nodeName) || /^[a-z][a-z0-9_.-]*-[a-z0-9_.-]*$/.test(nodeName)) {
        return true;
      }
    }
    return false;
  };
  'use strict';
  axe.utils.isXHTML = function(doc) {
    'use strict';
    if (!doc.createElement) {
      return false;
    }
    return doc.createElement('A').localName === 'A';
  };
  'use strict';
  function matchesTag(vNode, exp) {
    return vNode.props.nodeType === 1 && (exp.tag === '*' || vNode.props.nodeName === exp.tag);
  }
  function matchesClasses(vNode, exp) {
    return !exp.classes || exp.classes.every(function(cl) {
      return vNode.hasClass(cl.value);
    });
  }
  function matchesAttributes(vNode, exp) {
    return !exp.attributes || exp.attributes.every(function(att) {
      var nodeAtt = vNode.attr(att.key);
      return nodeAtt !== null && (!att.value || att.test(nodeAtt));
    });
  }
  function matchesId(vNode, exp) {
    return !exp.id || vNode.props.id === exp.id;
  }
  function matchesPseudos(target, exp) {
    if (!exp.pseudos || exp.pseudos.every(function(pseudo) {
      if (pseudo.name === 'not') {
        return !axe.utils.matchesExpression(target, pseudo.expressions[0]);
      }
      throw new Error('the pseudo selector ' + pseudo.name + ' has not yet been implemented');
    })) {
      return true;
    }
    return false;
  }
  function matchExpression(vNode, expression) {
    return matchesTag(vNode, expression) && matchesClasses(vNode, expression) && matchesAttributes(vNode, expression) && matchesId(vNode, expression) && matchesPseudos(vNode, expression);
  }
  var escapeRegExp = function() {
    var from = /(?=[\-\[\]{}()*+?.\\\^$|,#\s])/g;
    var to = '\\';
    return function(string) {
      return string.replace(from, to);
    };
  }();
  var reUnescape = /\\/g;
  function convertAttributes(atts) {
    if (!atts) {
      return;
    }
    return atts.map(function(att) {
      var attributeKey = att.name.replace(reUnescape, '');
      var attributeValue = (att.value || '').replace(reUnescape, '');
      var test, regexp;
      switch (att.operator) {
       case '^=':
        regexp = new RegExp('^' + escapeRegExp(attributeValue));
        break;

       case '$=':
        regexp = new RegExp(escapeRegExp(attributeValue) + '$');
        break;

       case '~=':
        regexp = new RegExp('(^|\\s)' + escapeRegExp(attributeValue) + '(\\s|$)');
        break;

       case '|=':
        regexp = new RegExp('^' + escapeRegExp(attributeValue) + '(-|$)');
        break;

       case '=':
        test = function test(value) {
          return attributeValue === value;
        };
        break;

       case '*=':
        test = function test(value) {
          return value && value.includes(attributeValue);
        };
        break;

       case '!=':
        test = function test(value) {
          return attributeValue !== value;
        };
        break;

       default:
        test = function test(value) {
          return !!value;
        };
      }
      if (attributeValue === '' && /^[*$^]=$/.test(att.operator)) {
        test = function test() {
          return false;
        };
      }
      if (!test) {
        test = function test(value) {
          return value && regexp.test(value);
        };
      }
      return {
        key: attributeKey,
        value: attributeValue,
        test: test
      };
    });
  }
  function convertClasses(classes) {
    if (!classes) {
      return;
    }
    return classes.map(function(className) {
      className = className.replace(reUnescape, '');
      return {
        value: className,
        regexp: new RegExp('(^|\\s)' + escapeRegExp(className) + '(\\s|$)')
      };
    });
  }
  function convertPseudos(pseudos) {
    if (!pseudos) {
      return;
    }
    return pseudos.map(function(p) {
      var expressions;
      if (p.name === 'not') {
        expressions = p.value;
        expressions = expressions.selectors ? expressions.selectors : [ expressions ];
        expressions = convertExpressions(expressions);
      }
      return {
        name: p.name,
        expressions: expressions,
        value: p.value
      };
    });
  }
  function convertExpressions(expressions) {
    return expressions.map(function(exp) {
      var newExp = [];
      var rule = exp.rule;
      while (rule) {
        newExp.push({
          tag: rule.tagName ? rule.tagName.toLowerCase() : '*',
          combinator: rule.nestingOperator ? rule.nestingOperator : ' ',
          id: rule.id,
          attributes: convertAttributes(rule.attrs),
          classes: convertClasses(rule.classNames),
          pseudos: convertPseudos(rule.pseudos)
        });
        rule = rule.rule;
      }
      return newExp;
    });
  }
  axe.utils.convertSelector = function convertSelector(selector) {
    var expressions = axe.utils.cssParser.parse(selector);
    expressions = expressions.selectors ? expressions.selectors : [ expressions ];
    return convertExpressions(expressions);
  };
  axe.utils.matchesExpression = function matchesExpression(vNode, expressions, matchAnyParent) {
    var exps = [].concat(expressions);
    var expression = exps.pop();
    var matches = matchExpression(vNode, expression);
    while (!matches && matchAnyParent && vNode.parent) {
      vNode = vNode.parent;
      matches = matchExpression(vNode, expression);
    }
    if (exps.length) {
      if ([ ' ', '>' ].includes(expression.combinator) === false) {
        throw new Error('axe.utils.matchesExpression does not support the combinator: ' + expression.combinator);
      }
      matches = matches && axe.utils.matchesExpression(vNode.parent, exps, expression.combinator === ' ');
    }
    return matches;
  };
  axe.utils.matches = function matches(vNode, selector) {
    var expressions = axe.utils.convertSelector(selector);
    return expressions.some(function(expression) {
      return axe.utils.matchesExpression(vNode, expression);
    });
  };
  'use strict';
  axe._memoizedFns = [];
  axe.utils.memoize = function(fn) {
    var memoized = axe.imports.memoize(fn);
    axe._memoizedFns.push(memoized);
    return memoized;
  };
  'use strict';
  function pushFrame(resultSet, options, frameElement, frameSelector) {
    'use strict';
    var frameXpath = axe.utils.getXpath(frameElement);
    var frameSpec = {
      element: frameElement,
      selector: frameSelector,
      xpath: frameXpath
    };
    resultSet.forEach(function(res) {
      res.node = axe.utils.DqElement.fromFrame(res.node, options, frameSpec);
      var checks = axe.utils.getAllChecks(res);
      if (checks.length) {
        checks.forEach(function(check) {
          check.relatedNodes = check.relatedNodes.map(function(node) {
            return axe.utils.DqElement.fromFrame(node, options, frameSpec);
          });
        });
      }
    });
  }
  function spliceNodes(target, to) {
    'use strict';
    var firstFromFrame = to[0].node, sorterResult, t;
    for (var i = 0, l = target.length; i < l; i++) {
      t = target[i].node;
      sorterResult = axe.utils.nodeSorter({
        actualNode: t.element
      }, {
        actualNode: firstFromFrame.element
      });
      if (sorterResult > 0 || sorterResult === 0 && firstFromFrame.selector.length < t.selector.length) {
        target.splice.apply(target, [ i, 0 ].concat(to));
        return;
      }
    }
    target.push.apply(target, to);
  }
  function normalizeResult(result) {
    'use strict';
    if (!result || !result.results) {
      return null;
    }
    if (!Array.isArray(result.results)) {
      return [ result.results ];
    }
    if (!result.results.length) {
      return null;
    }
    return result.results;
  }
  axe.utils.mergeResults = function mergeResults(frameResults, options) {
    'use strict';
    var result = [];
    frameResults.forEach(function(frameResult) {
      var results = normalizeResult(frameResult);
      if (!results || !results.length) {
        return;
      }
      results.forEach(function(ruleResult) {
        if (ruleResult.nodes && frameResult.frame) {
          pushFrame(ruleResult.nodes, options, frameResult.frameElement, frameResult.frame);
        }
        var res = axe.utils.findBy(result, 'id', ruleResult.id);
        if (!res) {
          result.push(ruleResult);
        } else {
          if (ruleResult.nodes.length) {
            spliceNodes(res.nodes, ruleResult.nodes);
          }
        }
      });
    });
    return result;
  };
  'use strict';
  axe.utils.nodeSorter = function nodeSorter(nodeA, nodeB) {
    nodeA = nodeA.actualNode || nodeA;
    nodeB = nodeB.actualNode || nodeB;
    if (nodeA === nodeB) {
      return 0;
    }
    if (nodeA.compareDocumentPosition(nodeB) & 4) {
      return -1;
    } else {
      return 1;
    }
  };
  'use strict';
  axe.utils.parseCrossOriginStylesheet = function parseCrossOriginStylesheet(url, options, priority, importedUrls, isCrossOrigin) {
    var axiosOptions = {
      method: 'get',
      timeout: axe.constants.preload.timeout,
      url: url
    };
    importedUrls.push(url);
    return axe.imports.axios(axiosOptions).then(function(_ref) {
      var data = _ref.data;
      var result = options.convertDataToStylesheet({
        data: data,
        isCrossOrigin: isCrossOrigin,
        priority: priority,
        root: options.rootNode,
        shadowId: options.shadowId
      });
      return axe.utils.parseStylesheet(result.sheet, options, priority, importedUrls, result.isCrossOrigin);
    });
  };
  'use strict';
  function _toConsumableArray(arr) {
    return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _nonIterableSpread();
  }
  function _nonIterableSpread() {
    throw new TypeError('Invalid attempt to spread non-iterable instance');
  }
  function _iterableToArray(iter) {
    if (Symbol.iterator in Object(iter) || Object.prototype.toString.call(iter) === '[object Arguments]') {
      return Array.from(iter);
    }
  }
  function _arrayWithoutHoles(arr) {
    if (Array.isArray(arr)) {
      for (var i = 0, arr2 = new Array(arr.length); i < arr.length; i++) {
        arr2[i] = arr[i];
      }
      return arr2;
    }
  }
  axe.utils.parseSameOriginStylesheet = function parseSameOriginStylesheet(sheet, options, priority, importedUrls) {
    var isCrossOrigin = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : false;
    var rules = Array.from(sheet.cssRules);
    if (!rules) {
      return Promise.resolve();
    }
    var cssImportRules = rules.filter(function(r) {
      return r.type === 3;
    });
    if (!cssImportRules.length) {
      return Promise.resolve({
        isCrossOrigin: isCrossOrigin,
        priority: priority,
        root: options.rootNode,
        shadowId: options.shadowId,
        sheet: sheet
      });
    }
    var cssImportUrlsNotAlreadyImported = cssImportRules.filter(function(rule) {
      return rule.href;
    }).map(function(rule) {
      return rule.href;
    }).filter(function(url) {
      return !importedUrls.includes(url);
    });
    var promises = cssImportUrlsNotAlreadyImported.map(function(importUrl, cssRuleIndex) {
      var newPriority = [].concat(_toConsumableArray(priority), [ cssRuleIndex ]);
      var isCrossOriginRequest = /^https?:\/\/|^\/\//i.test(importUrl);
      return axe.utils.parseCrossOriginStylesheet(importUrl, options, newPriority, importedUrls, isCrossOriginRequest);
    });
    var nonImportCSSRules = rules.filter(function(r) {
      return r.type !== 3;
    });
    if (!nonImportCSSRules.length) {
      return Promise.all(promises);
    }
    promises.push(Promise.resolve(options.convertDataToStylesheet({
      data: nonImportCSSRules.map(function(rule) {
        return rule.cssText;
      }).join(),
      isCrossOrigin: isCrossOrigin,
      priority: priority,
      root: options.rootNode,
      shadowId: options.shadowId
    })));
    return Promise.all(promises);
  };
  'use strict';
  axe.utils.parseStylesheet = function parseStylesheet(sheet, options, priority, importedUrls) {
    var isCrossOrigin = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : false;
    var isSameOrigin = isSameOriginStylesheet(sheet);
    if (isSameOrigin) {
      return axe.utils.parseSameOriginStylesheet(sheet, options, priority, importedUrls, isCrossOrigin);
    }
    return axe.utils.parseCrossOriginStylesheet(sheet.href, options, priority, importedUrls, true);
  };
  function isSameOriginStylesheet(sheet) {
    try {
      var rules = sheet.cssRules;
      if (!rules && sheet.href) {
        return false;
      }
      return true;
    } catch (e) {
      return false;
    }
  }
  'use strict';
  utils.performanceTimer = function() {
    'use strict';
    function now() {
      if (window.performance && window.performance) {
        return window.performance.now();
      }
    }
    var originalTime = null;
    var lastRecordedTime = now();
    return {
      start: function start() {
        this.mark('mark_axe_start');
      },
      end: function end() {
        this.mark('mark_axe_end');
        this.measure('axe', 'mark_axe_start', 'mark_axe_end');
        this.logMeasures('axe');
      },
      auditStart: function auditStart() {
        this.mark('mark_audit_start');
      },
      auditEnd: function auditEnd() {
        this.mark('mark_audit_end');
        this.measure('audit_start_to_end', 'mark_audit_start', 'mark_audit_end');
        this.logMeasures();
      },
      mark: function mark(markName) {
        if (window.performance && window.performance.mark !== undefined) {
          window.performance.mark(markName);
        }
      },
      measure: function measure(measureName, startMark, endMark) {
        if (window.performance && window.performance.measure !== undefined) {
          window.performance.measure(measureName, startMark, endMark);
        }
      },
      logMeasures: function logMeasures(measureName) {
        function log(req) {
          axe.log('Measure ' + req.name + ' took ' + req.duration + 'ms');
        }
        if (window.performance && window.performance.getEntriesByType !== undefined) {
          var axeStart = window.performance.getEntriesByName('mark_axe_start')[0];
          var measures = window.performance.getEntriesByType('measure').filter(function(measure) {
            return measure.startTime >= axeStart.startTime;
          });
          for (var i = 0; i < measures.length; ++i) {
            var req = measures[i];
            if (req.name === measureName) {
              log(req);
              return;
            }
            log(req);
          }
        }
      },
      timeElapsed: function timeElapsed() {
        return now() - lastRecordedTime;
      },
      reset: function reset() {
        if (!originalTime) {
          originalTime = now();
        }
        lastRecordedTime = now();
      }
    };
  }();
  'use strict';
  if (typeof Object.assign !== 'function') {
    (function() {
      Object.assign = function(target) {
        'use strict';
        if (target === undefined || target === null) {
          throw new TypeError('Cannot convert undefined or null to object');
        }
        var output = Object(target);
        for (var index = 1; index < arguments.length; index++) {
          var source = arguments[index];
          if (source !== undefined && source !== null) {
            for (var nextKey in source) {
              if (source.hasOwnProperty(nextKey)) {
                output[nextKey] = source[nextKey];
              }
            }
          }
        }
        return output;
      };
    })();
  }
  if (!Array.prototype.find) {
    Object.defineProperty(Array.prototype, 'find', {
      value: function value(predicate) {
        if (this === null) {
          throw new TypeError('Array.prototype.find called on null or undefined');
        }
        if (typeof predicate !== 'function') {
          throw new TypeError('predicate must be a function');
        }
        var list = Object(this);
        var length = list.length >>> 0;
        var thisArg = arguments[1];
        var value;
        for (var i = 0; i < length; i++) {
          value = list[i];
          if (predicate.call(thisArg, value, i, list)) {
            return value;
          }
        }
        return undefined;
      }
    });
  }
  axe.utils.pollyfillElementsFromPoint = function() {
    if (document.elementsFromPoint) {
      return document.elementsFromPoint;
    }
    if (document.msElementsFromPoint) {
      return document.msElementsFromPoint;
    }
    var usePointer = function() {
      var element = document.createElement('x');
      element.style.cssText = 'pointer-events:auto';
      return element.style.pointerEvents === 'auto';
    }();
    var cssProp = usePointer ? 'pointer-events' : 'visibility';
    var cssDisableVal = usePointer ? 'none' : 'hidden';
    var style = document.createElement('style');
    style.innerHTML = usePointer ? '* { pointer-events: all }' : '* { visibility: visible }';
    return function(x, y) {
      var current, i, d;
      var elements = [];
      var previousPointerEvents = [];
      document.head.appendChild(style);
      while ((current = document.elementFromPoint(x, y)) && elements.indexOf(current) === -1) {
        elements.push(current);
        previousPointerEvents.push({
          value: current.style.getPropertyValue(cssProp),
          priority: current.style.getPropertyPriority(cssProp)
        });
        current.style.setProperty(cssProp, cssDisableVal, 'important');
      }
      if (elements.indexOf(document.documentElement) < elements.length - 1) {
        elements.splice(elements.indexOf(document.documentElement), 1);
        elements.push(document.documentElement);
      }
      for (i = previousPointerEvents.length; !!(d = previousPointerEvents[--i]); ) {
        elements[i].style.setProperty(cssProp, d.value ? d.value : '', d.priority);
      }
      document.head.removeChild(style);
      return elements;
    };
  };
  if (typeof window.addEventListener === 'function') {
    document.elementsFromPoint = axe.utils.pollyfillElementsFromPoint();
  }
  if (!Array.prototype.includes) {
    Object.defineProperty(Array.prototype, 'includes', {
      value: function value(searchElement) {
        'use strict';
        var O = Object(this);
        var len = parseInt(O.length, 10) || 0;
        if (len === 0) {
          return false;
        }
        var n = parseInt(arguments[1], 10) || 0;
        var k;
        if (n >= 0) {
          k = n;
        } else {
          k = len + n;
          if (k < 0) {
            k = 0;
          }
        }
        var currentElement;
        while (k < len) {
          currentElement = O[k];
          if (searchElement === currentElement || searchElement !== searchElement && currentElement !== currentElement) {
            return true;
          }
          k++;
        }
        return false;
      }
    });
  }
  if (!Array.prototype.some) {
    Object.defineProperty(Array.prototype, 'some', {
      value: function value(fun) {
        'use strict';
        if (this == null) {
          throw new TypeError('Array.prototype.some called on null or undefined');
        }
        if (typeof fun !== 'function') {
          throw new TypeError();
        }
        var t = Object(this);
        var len = t.length >>> 0;
        var thisArg = arguments.length >= 2 ? arguments[1] : void 0;
        for (var i = 0; i < len; i++) {
          if (i in t && fun.call(thisArg, t[i], i, t)) {
            return true;
          }
        }
        return false;
      }
    });
  }
  if (!Array.from) {
    Object.defineProperty(Array, 'from', {
      value: function() {
        var toStr = Object.prototype.toString;
        var isCallable = function isCallable(fn) {
          return typeof fn === 'function' || toStr.call(fn) === '[object Function]';
        };
        var toInteger = function toInteger(value) {
          var number = Number(value);
          if (isNaN(number)) {
            return 0;
          }
          if (number === 0 || !isFinite(number)) {
            return number;
          }
          return (number > 0 ? 1 : -1) * Math.floor(Math.abs(number));
        };
        var maxSafeInteger = Math.pow(2, 53) - 1;
        var toLength = function toLength(value) {
          var len = toInteger(value);
          return Math.min(Math.max(len, 0), maxSafeInteger);
        };
        return function from(arrayLike) {
          var C = this;
          var items = Object(arrayLike);
          if (arrayLike == null) {
            throw new TypeError('Array.from requires an array-like object - not null or undefined');
          }
          var mapFn = arguments.length > 1 ? arguments[1] : void undefined;
          var T;
          if (typeof mapFn !== 'undefined') {
            if (!isCallable(mapFn)) {
              throw new TypeError('Array.from: when provided, the second argument must be a function');
            }
            if (arguments.length > 2) {
              T = arguments[2];
            }
          }
          var len = toLength(items.length);
          var A = isCallable(C) ? Object(new C(len)) : new Array(len);
          var k = 0;
          var kValue;
          while (k < len) {
            kValue = items[k];
            if (mapFn) {
              A[k] = typeof T === 'undefined' ? mapFn(kValue, k) : mapFn.call(T, kValue, k);
            } else {
              A[k] = kValue;
            }
            k += 1;
          }
          A.length = len;
          return A;
        };
      }()
    });
  }
  if (!String.prototype.includes) {
    String.prototype.includes = function(search, start) {
      if (typeof start !== 'number') {
        start = 0;
      }
      if (start + search.length > this.length) {
        return false;
      } else {
        return this.indexOf(search, start) !== -1;
      }
    };
  }
  'use strict';
  axe.utils.preloadCssom = function preloadCssom(_ref) {
    var _ref$treeRoot = _ref.treeRoot, treeRoot = _ref$treeRoot === void 0 ? axe._tree[0] : _ref$treeRoot;
    var rootNodes = getAllRootNodesInTree(treeRoot);
    if (!rootNodes.length) {
      return Promise.resolve();
    }
    var dynamicDoc = document.implementation.createHTMLDocument('Dynamic document for loading cssom');
    var convertDataToStylesheet = axe.utils.getStyleSheetFactory(dynamicDoc);
    return getCssomForAllRootNodes(rootNodes, convertDataToStylesheet).then(function(assets) {
      return flattenAssets(assets);
    });
  };
  function getAllRootNodesInTree(tree) {
    var ids = [];
    var rootNodes = axe.utils.querySelectorAllFilter(tree, '*', function(node) {
      if (ids.includes(node.shadowId)) {
        return false;
      }
      ids.push(node.shadowId);
      return true;
    }).map(function(node) {
      return {
        shadowId: node.shadowId,
        rootNode: axe.utils.getRootNode(node.actualNode)
      };
    });
    return axe.utils.uniqueArray(rootNodes, []);
  }
  function getCssomForAllRootNodes(rootNodes, convertDataToStylesheet) {
    var promises = [];
    rootNodes.forEach(function(_ref2, index) {
      var rootNode = _ref2.rootNode, shadowId = _ref2.shadowId;
      var sheets = getStylesheetsOfRootNode(rootNode, shadowId, convertDataToStylesheet);
      if (!sheets) {
        return Promise.all(promises);
      }
      var rootIndex = index + 1;
      var parseOptions = {
        rootNode: rootNode,
        shadowId: shadowId,
        convertDataToStylesheet: convertDataToStylesheet,
        rootIndex: rootIndex
      };
      var importedUrls = [];
      var p = Promise.all(sheets.map(function(sheet, sheetIndex) {
        var priority = [ rootIndex, sheetIndex ];
        return axe.utils.parseStylesheet(sheet, parseOptions, priority, importedUrls);
      }));
      promises.push(p);
    });
    return Promise.all(promises);
  }
  function flattenAssets(assets) {
    return assets.reduce(function(acc, val) {
      return Array.isArray(val) ? acc.concat(flattenAssets(val)) : acc.concat(val);
    }, []);
  }
  function getStylesheetsOfRootNode(rootNode, shadowId, convertDataToStylesheet) {
    var sheets;
    if (rootNode.nodeType === 11 && shadowId) {
      sheets = getStylesheetsFromDocumentFragment(rootNode, convertDataToStylesheet);
    } else {
      sheets = getStylesheetsFromDocument(rootNode);
    }
    return filterStylesheetsWithSameHref(sheets);
  }
  function getStylesheetsFromDocumentFragment(rootNode, convertDataToStylesheet) {
    return Array.from(rootNode.children).filter(filerStyleAndLinkAttributesInDocumentFragment).reduce(function(out, node) {
      var nodeName = node.nodeName.toUpperCase();
      var data = nodeName === 'STYLE' ? node.textContent : node;
      var isLink = nodeName === 'LINK';
      var stylesheet = convertDataToStylesheet({
        data: data,
        isLink: isLink,
        root: rootNode
      });
      out.push(stylesheet.sheet);
      return out;
    }, []);
  }
  function getStylesheetsFromDocument(rootNode) {
    return Array.from(rootNode.styleSheets).filter(function(sheet) {
      return filterMediaIsPrint(sheet.media.mediaText);
    });
  }
  function filerStyleAndLinkAttributesInDocumentFragment(node) {
    var nodeName = node.nodeName.toUpperCase();
    var linkHref = node.getAttribute('href');
    var linkRel = node.getAttribute('rel');
    var isLink = nodeName === 'LINK' && linkHref && linkRel && node.rel.toUpperCase().includes('STYLESHEET');
    var isStyle = nodeName === 'STYLE';
    return isStyle || isLink && filterMediaIsPrint(node.media);
  }
  function filterMediaIsPrint(media) {
    if (!media) {
      return true;
    }
    return !media.toUpperCase().includes('PRINT');
  }
  function filterStylesheetsWithSameHref(sheets) {
    var hrefs = [];
    return sheets.filter(function(sheet) {
      if (!sheet.href) {
        return true;
      }
      if (hrefs.includes(sheet.href)) {
        return false;
      }
      hrefs.push(sheet.href);
      return true;
    });
  }
  'use strict';
  axe.utils.preloadMedia = function preloadMedia(_ref) {
    var _ref$treeRoot = _ref.treeRoot, treeRoot = _ref$treeRoot === void 0 ? axe._tree[0] : _ref$treeRoot;
    var mediaVirtualNodes = axe.utils.querySelectorAllFilter(treeRoot, 'video, audio', function(_ref2) {
      var actualNode = _ref2.actualNode;
      if (actualNode.hasAttribute('src')) {
        return !!actualNode.getAttribute('src');
      }
      var sourceWithSrc = Array.from(actualNode.getElementsByTagName('source')).filter(function(source) {
        return !!source.getAttribute('src');
      });
      if (sourceWithSrc.length <= 0) {
        return false;
      }
      return true;
    });
    return Promise.all(mediaVirtualNodes.map(function(_ref3) {
      var actualNode = _ref3.actualNode;
      return isMediaElementReady(actualNode);
    }));
  };
  function isMediaElementReady(elm) {
    return new Promise(function(resolve) {
      if (elm.readyState > 0) {
        resolve(elm);
      }
      function onMediaReady() {
        elm.removeEventListener('loadedmetadata', onMediaReady);
        resolve(elm);
      }
      elm.addEventListener('loadedmetadata', onMediaReady);
    });
  }
  'use strict';
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  function _defineProperty(obj, key, value) {
    if (key in obj) {
      Object.defineProperty(obj, key, {
        value: value,
        enumerable: true,
        configurable: true,
        writable: true
      });
    } else {
      obj[key] = value;
    }
    return obj;
  }
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  function isValidPreloadObject(preload) {
    return _typeof(preload) === 'object' && Array.isArray(preload.assets);
  }
  axe.utils.shouldPreload = function shouldPreload(options) {
    if (!options || options.preload === undefined || options.preload === null) {
      return true;
    }
    if (typeof options.preload === 'boolean') {
      return options.preload;
    }
    return isValidPreloadObject(options.preload);
  };
  axe.utils.getPreloadConfig = function getPreloadConfig(options) {
    var _axe$constants$preloa = axe.constants.preload, assets = _axe$constants$preloa.assets, timeout = _axe$constants$preloa.timeout;
    var config = {
      assets: assets,
      timeout: timeout
    };
    if (!options.preload) {
      return config;
    }
    if (typeof options.preload === 'boolean') {
      return config;
    }
    var areRequestedAssetsValid = options.preload.assets.every(function(a) {
      return assets.includes(a.toLowerCase());
    });
    if (!areRequestedAssetsValid) {
      throw new Error('Requested assets, not supported. ' + 'Supported assets are: '.concat(assets.join(', '), '.'));
    }
    config.assets = axe.utils.uniqueArray(options.preload.assets.map(function(a) {
      return a.toLowerCase();
    }), []);
    if (options.preload.timeout && typeof options.preload.timeout === 'number' && !isNaN(options.preload.timeout)) {
      config.timeout = options.preload.timeout;
    }
    return config;
  };
  axe.utils.preload = function preload(options) {
    var preloadFunctionsMap = {
      cssom: axe.utils.preloadCssom,
      media: axe.utils.preloadMedia
    };
    var shouldPreload = axe.utils.shouldPreload(options);
    if (!shouldPreload) {
      return Promise.resolve();
    }
    return new Promise(function(resolve, reject) {
      var _axe$utils$getPreload = axe.utils.getPreloadConfig(options), assets = _axe$utils$getPreload.assets, timeout = _axe$utils$getPreload.timeout;
      var preloadTimeout = setTimeout(function() {
        return reject(new Error('Preload assets timed out.'));
      }, timeout);
      Promise.all(assets.map(function(asset) {
        return preloadFunctionsMap[asset](options).then(function(results) {
          return _defineProperty({}, asset, results);
        });
      })).then(function(results) {
        var preloadAssets = results.reduce(function(out, result) {
          return _extends({}, out, {}, result);
        }, {});
        clearTimeout(preloadTimeout);
        resolve(preloadAssets);
      })['catch'](function(err) {
        clearTimeout(preloadTimeout);
        reject(err);
      });
    });
  };
  'use strict';
  var dataRegex = /\$\{\s?data\s?\}/g;
  function substitute(str, data) {
    if (typeof data === 'string') {
      return str.replace(dataRegex, data);
    }
    for (var prop in data) {
      if (data.hasOwnProperty(prop)) {
        var regex = new RegExp('\\${\\s?data\\.' + prop + '\\s?}', 'g');
        str = str.replace(regex, data[prop]);
      }
    }
    return str;
  }
  axe.utils.processMessage = function processMessage(message, data) {
    if (!message) {
      return;
    }
    if (Array.isArray(data)) {
      data.values = data.join(', ');
      if (typeof message.singular === 'string' && typeof message.plural === 'string') {
        var _str = data.length === 1 ? message.singular : message.plural;
        return substitute(_str, data);
      }
      return substitute(message, data);
    }
    if (typeof message === 'string') {
      return substitute(message, data);
    }
    if (typeof data === 'string') {
      var _str2 = message[data];
      return substitute(_str2, data);
    }
    var str = message['default'] || helpers.incompleteFallbackMessage();
    if (data && data.messageKey && message[data.messageKey]) {
      str = message[data.messageKey];
    }
    return processMessage(str, data);
  };
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  function getIncompleteReason(checkData, messages) {
    function getDefaultMsg(messages) {
      if (messages.incomplete && messages.incomplete['default']) {
        return messages.incomplete['default'];
      } else {
        return helpers.incompleteFallbackMessage();
      }
    }
    if (checkData && checkData.missingData) {
      try {
        var msg = messages.incomplete[checkData.missingData[0].reason];
        if (!msg) {
          throw new Error();
        }
        return msg;
      } catch (e) {
        if (typeof checkData.missingData === 'string') {
          return messages.incomplete[checkData.missingData];
        } else {
          return getDefaultMsg(messages);
        }
      }
    } else if (checkData && checkData.messageKey) {
      return messages.incomplete[checkData.messageKey];
    } else {
      return getDefaultMsg(messages);
    }
  }
  function extender(checksData, shouldBeTrue) {
    'use strict';
    return function(check) {
      var sourceData = checksData[check.id] || {};
      var messages = sourceData.messages || {};
      var data = Object.assign({}, sourceData);
      delete data.messages;
      if (check.result === undefined) {
        if (_typeof(messages.incomplete) === 'object' && !Array.isArray(check.data)) {
          data.message = getIncompleteReason(check.data, messages);
        }
        if (!data.message) {
          data.message = messages.incomplete;
        }
      } else {
        data.message = check.result === shouldBeTrue ? messages.pass : messages.fail;
      }
      if (typeof data.message !== 'function') {
        data.message = axe.utils.processMessage(data.message, check.data);
      }
      axe.utils.extendMetaData(check, data);
    };
  }
  axe.utils.publishMetaData = function(ruleResult) {
    'use strict';
    var checksData = axe._audit.data.checks || {};
    var rulesData = axe._audit.data.rules || {};
    var rule = axe.utils.findBy(axe._audit.rules, 'id', ruleResult.id) || {};
    ruleResult.tags = axe.utils.clone(rule.tags || []);
    var shouldBeTrue = extender(checksData, true);
    var shouldBeFalse = extender(checksData, false);
    ruleResult.nodes.forEach(function(detail) {
      detail.any.forEach(shouldBeTrue);
      detail.all.forEach(shouldBeTrue);
      detail.none.forEach(shouldBeFalse);
    });
    axe.utils.extendMetaData(ruleResult, axe.utils.clone(rulesData[ruleResult.id] || {}));
  };
  'use strict';
  function createLocalVariables(vNodes, anyLevel, thisLevel, parentShadowId) {
    var retVal = {
      vNodes: vNodes.slice(),
      anyLevel: anyLevel,
      thisLevel: thisLevel,
      parentShadowId: parentShadowId
    };
    retVal.vNodes.reverse();
    return retVal;
  }
  function matchExpressions(domTree, expressions, filter) {
    var stack = [];
    var vNodes = Array.isArray(domTree) ? domTree : [ domTree ];
    var currentLevel = createLocalVariables(vNodes, expressions, [], domTree[0].shadowId);
    var result = [];
    while (currentLevel.vNodes.length) {
      var vNode = currentLevel.vNodes.pop();
      var childOnly = [];
      var childAny = [];
      var combined = currentLevel.anyLevel.slice().concat(currentLevel.thisLevel);
      var added = false;
      for (var i = 0; i < combined.length; i++) {
        var exp = combined[i];
        if ((!exp[0].id || vNode.shadowId === currentLevel.parentShadowId) && axe.utils.matchesExpression(vNode, exp[0])) {
          if (exp.length === 1) {
            if (!added && (!filter || filter(vNode))) {
              result.push(vNode);
              added = true;
            }
          } else {
            var rest = exp.slice(1);
            if ([ ' ', '>' ].includes(rest[0].combinator) === false) {
              throw new Error('axe.utils.querySelectorAll does not support the combinator: ' + exp[1].combinator);
            }
            if (rest[0].combinator === '>') {
              childOnly.push(rest);
            } else {
              childAny.push(rest);
            }
          }
        }
        if ((!exp[0].id || vNode.shadowId === currentLevel.parentShadowId) && currentLevel.anyLevel.includes(exp)) {
          childAny.push(exp);
        }
      }
      if (vNode.children && vNode.children.length) {
        stack.push(currentLevel);
        currentLevel = createLocalVariables(vNode.children, childAny, childOnly, vNode.shadowId);
      }
      while (!currentLevel.vNodes.length && stack.length) {
        currentLevel = stack.pop();
      }
    }
    return result;
  }
  axe.utils.querySelectorAll = function(domTree, selector) {
    return axe.utils.querySelectorAllFilter(domTree, selector);
  };
  axe.utils.querySelectorAllFilter = function(domTree, selector, filter) {
    domTree = Array.isArray(domTree) ? domTree : [ domTree ];
    var expressions = axe.utils.convertSelector(selector);
    return matchExpressions(domTree, expressions, filter);
  };
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  (function() {
    'use strict';
    function noop() {}
    function funcGuard(f) {
      if (typeof f !== 'function') {
        throw new TypeError('Queue methods require functions as arguments');
      }
    }
    function queue() {
      var tasks = [];
      var started = 0;
      var remaining = 0;
      var completeQueue = noop;
      var complete = false;
      var err;
      var defaultFail = function defaultFail(e) {
        err = e;
        setTimeout(function() {
          if (err !== undefined && err !== null) {
            axe.log('Uncaught error (of queue)', err);
          }
        }, 1);
      };
      var failed = defaultFail;
      function createResolve(i) {
        return function(r) {
          tasks[i] = r;
          remaining -= 1;
          if (!remaining && completeQueue !== noop) {
            complete = true;
            completeQueue(tasks);
          }
        };
      }
      function abort(msg) {
        completeQueue = noop;
        failed(msg);
        return tasks;
      }
      function pop() {
        var length = tasks.length;
        for (;started < length; started++) {
          var task = tasks[started];
          try {
            task.call(null, createResolve(started), abort);
          } catch (e) {
            abort(e);
          }
        }
      }
      var q = {
        defer: function defer(fn) {
          if (_typeof(fn) === 'object' && fn.then && fn['catch']) {
            var defer = fn;
            fn = function fn(resolve, reject) {
              defer.then(resolve)['catch'](reject);
            };
          }
          funcGuard(fn);
          if (err !== undefined) {
            return;
          } else if (complete) {
            throw new Error('Queue already completed');
          }
          tasks.push(fn);
          ++remaining;
          pop();
          return q;
        },
        then: function then(fn) {
          funcGuard(fn);
          if (completeQueue !== noop) {
            throw new Error('queue `then` already set');
          }
          if (!err) {
            completeQueue = fn;
            if (!remaining) {
              complete = true;
              completeQueue(tasks);
            }
          }
          return q;
        },
        catch: function _catch(fn) {
          funcGuard(fn);
          if (failed !== defaultFail) {
            throw new Error('queue `catch` already set');
          }
          if (!err) {
            failed = fn;
          } else {
            fn(err);
            err = null;
          }
          return q;
        },
        abort: abort
      };
      return q;
    }
    axe.utils.queue = queue;
  })();
  'use strict';
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  (function(exports) {
    'use strict';
    var messages = {}, subscribers = {}, errorTypes = Object.freeze([ 'EvalError', 'RangeError', 'ReferenceError', 'SyntaxError', 'TypeError', 'URIError' ]);
    function _getSource() {
      var application = 'axeAPI', version = '', src;
      if (typeof axe !== 'undefined' && axe._audit && axe._audit.application) {
        application = axe._audit.application;
      }
      if (typeof axe !== 'undefined') {
        version = axe.version;
      }
      src = application + '.' + version;
      return src;
    }
    function verify(postedMessage) {
      if (_typeof(postedMessage) === 'object' && typeof postedMessage.uuid === 'string' && postedMessage._respondable === true) {
        var messageSource = _getSource();
        return postedMessage._source === messageSource || postedMessage._source === 'axeAPI.x.y.z' || messageSource === 'axeAPI.x.y.z';
      }
      return false;
    }
    function post(win, topic, message, uuid, keepalive, callback) {
      var error;
      if (message instanceof Error) {
        error = {
          name: message.name,
          message: message.message,
          stack: message.stack
        };
        message = undefined;
      }
      var data = {
        uuid: uuid,
        topic: topic,
        message: message,
        error: error,
        _respondable: true,
        _source: _getSource(),
        _axeuuid: axe._uuid,
        _keepalive: keepalive
      };
      var axeRespondables = axe._cache.get('axeRespondables');
      if (!axeRespondables) {
        axeRespondables = {};
        axe._cache.set('axeRespondables', axeRespondables);
      }
      axeRespondables[uuid] = true;
      if (typeof callback === 'function') {
        messages[uuid] = callback;
      }
      win.postMessage(JSON.stringify(data), '*');
    }
    function respondable(win, topic, message, keepalive, callback) {
      var id = uuid.v1();
      post(win, topic, message, id, keepalive, callback);
    }
    respondable.subscribe = function(topic, callback) {
      subscribers[topic] = callback;
    };
    respondable.isInFrame = function(win) {
      win = win || window;
      return !!win.frameElement;
    };
    function createResponder(source, topic, uuid) {
      return function(message, keepalive, callback) {
        post(source, topic, message, uuid, keepalive, callback);
      };
    }
    function publish(source, data, keepalive) {
      var topic = data.topic;
      var subscriber = subscribers[topic];
      if (subscriber) {
        var responder = createResponder(source, null, data.uuid);
        subscriber(data.message, keepalive, responder);
      }
    }
    function buildErrorObject(error) {
      var msg = error.message || 'Unknown error occurred';
      var errorName = errorTypes.includes(error.name) ? error.name : 'Error';
      var ErrConstructor = window[errorName] || Error;
      if (error.stack) {
        msg += '\n' + error.stack.replace(error.message, '');
      }
      return new ErrConstructor(msg);
    }
    function parseMessage(dataString) {
      var data;
      if (typeof dataString !== 'string') {
        return;
      }
      try {
        data = JSON.parse(dataString);
      } catch (ex) {}
      if (!verify(data)) {
        return;
      }
      if (_typeof(data.error) === 'object') {
        data.error = buildErrorObject(data.error);
      } else {
        data.error = undefined;
      }
      return data;
    }
    if (typeof window.addEventListener === 'function') {
      window.addEventListener('message', function(e) {
        var data = parseMessage(e.data);
        if (!data || !data._axeuuid) {
          return;
        }
        var uuid = data.uuid;
        var axeRespondables = axe._cache.get('axeRespondables') || {};
        if (axeRespondables[uuid] && data._axeuuid === axe._uuid) {
          return;
        }
        var keepalive = data._keepalive;
        var callback = messages[uuid];
        if (callback) {
          var result = data.error || data.message;
          var responder = createResponder(e.source, data.topic, uuid);
          callback(result, keepalive, responder);
          if (!keepalive) {
            delete messages[uuid];
          }
        }
        if (!data.error) {
          try {
            publish(e.source, data, keepalive);
          } catch (err) {
            post(e.source, null, err, uuid, false);
          }
        }
      }, false);
    }
    exports.respondable = respondable;
  })(utils);
  'use strict';
  function matchTags(rule, runOnly) {
    'use strict';
    var include, exclude, matching;
    var defaultExclude = axe._audit && axe._audit.tagExclude ? axe._audit.tagExclude : [];
    if (runOnly.hasOwnProperty('include') || runOnly.hasOwnProperty('exclude')) {
      include = runOnly.include || [];
      include = Array.isArray(include) ? include : [ include ];
      exclude = runOnly.exclude || [];
      exclude = Array.isArray(exclude) ? exclude : [ exclude ];
      exclude = exclude.concat(defaultExclude.filter(function(tag) {
        return include.indexOf(tag) === -1;
      }));
    } else {
      include = Array.isArray(runOnly) ? runOnly : [ runOnly ];
      exclude = defaultExclude.filter(function(tag) {
        return include.indexOf(tag) === -1;
      });
    }
    matching = include.some(function(tag) {
      return rule.tags.indexOf(tag) !== -1;
    });
    if (matching || include.length === 0 && rule.enabled !== false) {
      return exclude.every(function(tag) {
        return rule.tags.indexOf(tag) === -1;
      });
    } else {
      return false;
    }
  }
  axe.utils.ruleShouldRun = function(rule, context, options) {
    'use strict';
    var runOnly = options.runOnly || {};
    var ruleOptions = (options.rules || {})[rule.id];
    if (rule.pageLevel && !context.page) {
      return false;
    } else if (runOnly.type === 'rule') {
      return runOnly.values.indexOf(rule.id) !== -1;
    } else if (ruleOptions && typeof ruleOptions.enabled === 'boolean') {
      return ruleOptions.enabled;
    } else if (runOnly.type === 'tag' && runOnly.values) {
      return matchTags(rule, runOnly.values);
    } else {
      return matchTags(rule, []);
    }
  };
  'use strict';
  function setScroll(elm, top, left) {
    if (elm === window) {
      return elm.scroll(left, top);
    } else {
      elm.scrollTop = top;
      elm.scrollLeft = left;
    }
  }
  function getElmScrollRecursive(root) {
    return Array.from(root.children || root.childNodes || []).reduce(function(scrolls, elm) {
      var scroll = axe.utils.getScroll(elm);
      if (scroll) {
        scrolls.push(scroll);
      }
      return scrolls.concat(getElmScrollRecursive(elm));
    }, []);
  }
  axe.utils.getScrollState = function getScrollState() {
    var win = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : window;
    var root = win.document.documentElement;
    var windowScroll = [ win.pageXOffset !== undefined ? {
      elm: win,
      top: win.pageYOffset,
      left: win.pageXOffset
    } : {
      elm: root,
      top: root.scrollTop,
      left: root.scrollLeft
    } ];
    return windowScroll.concat(getElmScrollRecursive(document.body));
  };
  axe.utils.setScrollState = function setScrollState(scrollState) {
    scrollState.forEach(function(_ref) {
      var elm = _ref.elm, top = _ref.top, left = _ref.left;
      return setScroll(elm, top, left);
    });
  };
  'use strict';
  function getDeepest(collection) {
    'use strict';
    return collection.sort(function(a, b) {
      if (axe.utils.contains(a, b)) {
        return 1;
      }
      return -1;
    })[0];
  }
  function isNodeInContext(node, context) {
    'use strict';
    var include = context.include && getDeepest(context.include.filter(function(candidate) {
      return axe.utils.contains(candidate, node);
    }));
    var exclude = context.exclude && getDeepest(context.exclude.filter(function(candidate) {
      return axe.utils.contains(candidate, node);
    }));
    if (!exclude && include || exclude && axe.utils.contains(exclude, include)) {
      return true;
    }
    return false;
  }
  function pushNode(result, nodes) {
    'use strict';
    var temp;
    if (result.length === 0) {
      return nodes;
    }
    if (result.length < nodes.length) {
      temp = result;
      result = nodes;
      nodes = temp;
    }
    for (var i = 0, l = nodes.length; i < l; i++) {
      if (!result.includes(nodes[i])) {
        result.push(nodes[i]);
      }
    }
    return result;
  }
  function reduceIncludes(includes) {
    return includes.reduce(function(res, el) {
      if (!res.length || !axe.utils.contains(res[res.length - 1], el)) {
        res.push(el);
      }
      return res;
    }, []);
  }
  axe.utils.select = function select(selector, context) {
    'use strict';
    var result = [];
    var candidate;
    if (axe._selectCache) {
      for (var j = 0, l = axe._selectCache.length; j < l; j++) {
        var item = axe._selectCache[j];
        if (item.selector === selector) {
          return item.result;
        }
      }
    }
    var curried = function(context) {
      return function(node) {
        return isNodeInContext(node, context);
      };
    }(context);
    var reducedIncludes = reduceIncludes(context.include);
    for (var i = 0; i < reducedIncludes.length; i++) {
      candidate = reducedIncludes[i];
      result = pushNode(result, axe.utils.querySelectorAllFilter(candidate, selector, curried));
    }
    if (axe._selectCache) {
      axe._selectCache.push({
        selector: selector,
        result: result
      });
    }
    return result;
  };
  'use strict';
  axe.utils.toArray = function(thing) {
    'use strict';
    return Array.prototype.slice.call(thing);
  };
  axe.utils.uniqueArray = function(arr1, arr2) {
    return arr1.concat(arr2).filter(function(elem, pos, arr) {
      return arr.indexOf(elem) === pos;
    });
  };
  'use strict';
  axe.utils.tokenList = function(str) {
    'use strict';
    return str.trim().replace(/\s{2,}/g, ' ').split(' ');
  };
  'use strict';
  var uuid;
  (function(_global) {
    var _rng;
    var _crypto = _global.crypto || _global.msCrypto;
    if (!_rng && _crypto && _crypto.getRandomValues) {
      var _rnds8 = new Uint8Array(16);
      _rng = function whatwgRNG() {
        _crypto.getRandomValues(_rnds8);
        return _rnds8;
      };
    }
    if (!_rng) {
      var _rnds = new Array(16);
      _rng = function _rng() {
        for (var i = 0, r; i < 16; i++) {
          if ((i & 3) === 0) {
            r = Math.random() * 4294967296;
          }
          _rnds[i] = r >>> ((i & 3) << 3) & 255;
        }
        return _rnds;
      };
    }
    var BufferClass = typeof _global.Buffer == 'function' ? _global.Buffer : Array;
    var _byteToHex = [];
    var _hexToByte = {};
    for (var i = 0; i < 256; i++) {
      _byteToHex[i] = (i + 256).toString(16).substr(1);
      _hexToByte[_byteToHex[i]] = i;
    }
    function parse(s, buf, offset) {
      var i = buf && offset || 0, ii = 0;
      buf = buf || [];
      s.toLowerCase().replace(/[0-9a-f]{2}/g, function(oct) {
        if (ii < 16) {
          buf[i + ii++] = _hexToByte[oct];
        }
      });
      while (ii < 16) {
        buf[i + ii++] = 0;
      }
      return buf;
    }
    function unparse(buf, offset) {
      var i = offset || 0, bth = _byteToHex;
      return bth[buf[i++]] + bth[buf[i++]] + bth[buf[i++]] + bth[buf[i++]] + '-' + bth[buf[i++]] + bth[buf[i++]] + '-' + bth[buf[i++]] + bth[buf[i++]] + '-' + bth[buf[i++]] + bth[buf[i++]] + '-' + bth[buf[i++]] + bth[buf[i++]] + bth[buf[i++]] + bth[buf[i++]] + bth[buf[i++]] + bth[buf[i++]];
    }
    var _seedBytes = _rng();
    var _nodeId = [ _seedBytes[0] | 1, _seedBytes[1], _seedBytes[2], _seedBytes[3], _seedBytes[4], _seedBytes[5] ];
    var _clockseq = (_seedBytes[6] << 8 | _seedBytes[7]) & 16383;
    var _lastMSecs = 0, _lastNSecs = 0;
    function v1(options, buf, offset) {
      var i = buf && offset || 0;
      var b = buf || [];
      options = options || {};
      var clockseq = options.clockseq != null ? options.clockseq : _clockseq;
      var msecs = options.msecs != null ? options.msecs : new Date().getTime();
      var nsecs = options.nsecs != null ? options.nsecs : _lastNSecs + 1;
      var dt = msecs - _lastMSecs + (nsecs - _lastNSecs) / 1e4;
      if (dt < 0 && options.clockseq == null) {
        clockseq = clockseq + 1 & 16383;
      }
      if ((dt < 0 || msecs > _lastMSecs) && options.nsecs == null) {
        nsecs = 0;
      }
      if (nsecs >= 1e4) {
        throw new Error('uuid.v1(): Can\'t create more than 10M uuids/sec');
      }
      _lastMSecs = msecs;
      _lastNSecs = nsecs;
      _clockseq = clockseq;
      msecs += 122192928e5;
      var tl = ((msecs & 268435455) * 1e4 + nsecs) % 4294967296;
      b[i++] = tl >>> 24 & 255;
      b[i++] = tl >>> 16 & 255;
      b[i++] = tl >>> 8 & 255;
      b[i++] = tl & 255;
      var tmh = msecs / 4294967296 * 1e4 & 268435455;
      b[i++] = tmh >>> 8 & 255;
      b[i++] = tmh & 255;
      b[i++] = tmh >>> 24 & 15 | 16;
      b[i++] = tmh >>> 16 & 255;
      b[i++] = clockseq >>> 8 | 128;
      b[i++] = clockseq & 255;
      var node = options.node || _nodeId;
      for (var n = 0; n < 6; n++) {
        b[i + n] = node[n];
      }
      return buf ? buf : unparse(b);
    }
    function v4(options, buf, offset) {
      var i = buf && offset || 0;
      if (typeof options == 'string') {
        buf = options == 'binary' ? new BufferClass(16) : null;
        options = null;
      }
      options = options || {};
      var rnds = options.random || (options.rng || _rng)();
      rnds[6] = rnds[6] & 15 | 64;
      rnds[8] = rnds[8] & 63 | 128;
      if (buf) {
        for (var ii = 0; ii < 16; ii++) {
          buf[i + ii] = rnds[ii];
        }
      }
      return buf || unparse(rnds);
    }
    uuid = v4;
    uuid.v1 = v1;
    uuid.v4 = v4;
    uuid.parse = parse;
    uuid.unparse = unparse;
    uuid.BufferClass = BufferClass;
    axe._uuid = v1();
  })(window);
  'use strict';
  axe.utils.validInputTypes = function validInputTypes() {
    'use strict';
    return [ 'hidden', 'text', 'search', 'tel', 'url', 'email', 'password', 'date', 'month', 'week', 'time', 'datetime-local', 'number', 'range', 'color', 'checkbox', 'radio', 'file', 'submit', 'image', 'reset', 'button' ];
  };
  'use strict';
  var langs = [ 'aa', 'ab', 'ae', 'af', 'ak', 'am', 'an', 'ar', 'as', 'av', 'ay', 'az', 'ba', 'be', 'bg', 'bh', 'bi', 'bm', 'bn', 'bo', 'br', 'bs', 'ca', 'ce', 'ch', 'co', 'cr', 'cs', 'cu', 'cv', 'cy', 'da', 'de', 'dv', 'dz', 'ee', 'el', 'en', 'eo', 'es', 'et', 'eu', 'fa', 'ff', 'fi', 'fj', 'fo', 'fr', 'fy', 'ga', 'gd', 'gl', 'gn', 'gu', 'gv', 'ha', 'he', 'hi', 'ho', 'hr', 'ht', 'hu', 'hy', 'hz', 'ia', 'id', 'ie', 'ig', 'ii', 'ik', 'in', 'io', 'is', 'it', 'iu', 'iw', 'ja', 'ji', 'jv', 'jw', 'ka', 'kg', 'ki', 'kj', 'kk', 'kl', 'km', 'kn', 'ko', 'kr', 'ks', 'ku', 'kv', 'kw', 'ky', 'la', 'lb', 'lg', 'li', 'ln', 'lo', 'lt', 'lu', 'lv', 'mg', 'mh', 'mi', 'mk', 'ml', 'mn', 'mo', 'mr', 'ms', 'mt', 'my', 'na', 'nb', 'nd', 'ne', 'ng', 'nl', 'nn', 'no', 'nr', 'nv', 'ny', 'oc', 'oj', 'om', 'or', 'os', 'pa', 'pi', 'pl', 'ps', 'pt', 'qu', 'rm', 'rn', 'ro', 'ru', 'rw', 'sa', 'sc', 'sd', 'se', 'sg', 'sh', 'si', 'sk', 'sl', 'sm', 'sn', 'so', 'sq', 'sr', 'ss', 'st', 'su', 'sv', 'sw', 'ta', 'te', 'tg', 'th', 'ti', 'tk', 'tl', 'tn', 'to', 'tr', 'ts', 'tt', 'tw', 'ty', 'ug', 'uk', 'ur', 'uz', 've', 'vi', 'vo', 'wa', 'wo', 'xh', 'yi', 'yo', 'za', 'zh', 'zu', 'aaa', 'aab', 'aac', 'aad', 'aae', 'aaf', 'aag', 'aah', 'aai', 'aak', 'aal', 'aam', 'aan', 'aao', 'aap', 'aaq', 'aas', 'aat', 'aau', 'aav', 'aaw', 'aax', 'aaz', 'aba', 'abb', 'abc', 'abd', 'abe', 'abf', 'abg', 'abh', 'abi', 'abj', 'abl', 'abm', 'abn', 'abo', 'abp', 'abq', 'abr', 'abs', 'abt', 'abu', 'abv', 'abw', 'abx', 'aby', 'abz', 'aca', 'acb', 'acd', 'ace', 'acf', 'ach', 'aci', 'ack', 'acl', 'acm', 'acn', 'acp', 'acq', 'acr', 'acs', 'act', 'acu', 'acv', 'acw', 'acx', 'acy', 'acz', 'ada', 'adb', 'add', 'ade', 'adf', 'adg', 'adh', 'adi', 'adj', 'adl', 'adn', 'ado', 'adp', 'adq', 'adr', 'ads', 'adt', 'adu', 'adw', 'adx', 'ady', 'adz', 'aea', 'aeb', 'aec', 'aed', 'aee', 'aek', 'ael', 'aem', 'aen', 'aeq', 'aer', 'aes', 'aeu', 'aew', 'aey', 'aez', 'afa', 'afb', 'afd', 'afe', 'afg', 'afh', 'afi', 'afk', 'afn', 'afo', 'afp', 'afs', 'aft', 'afu', 'afz', 'aga', 'agb', 'agc', 'agd', 'age', 'agf', 'agg', 'agh', 'agi', 'agj', 'agk', 'agl', 'agm', 'agn', 'ago', 'agp', 'agq', 'agr', 'ags', 'agt', 'agu', 'agv', 'agw', 'agx', 'agy', 'agz', 'aha', 'ahb', 'ahg', 'ahh', 'ahi', 'ahk', 'ahl', 'ahm', 'ahn', 'aho', 'ahp', 'ahr', 'ahs', 'aht', 'aia', 'aib', 'aic', 'aid', 'aie', 'aif', 'aig', 'aih', 'aii', 'aij', 'aik', 'ail', 'aim', 'ain', 'aio', 'aip', 'aiq', 'air', 'ais', 'ait', 'aiw', 'aix', 'aiy', 'aja', 'ajg', 'aji', 'ajn', 'ajp', 'ajt', 'aju', 'ajw', 'ajz', 'akb', 'akc', 'akd', 'ake', 'akf', 'akg', 'akh', 'aki', 'akj', 'akk', 'akl', 'akm', 'ako', 'akp', 'akq', 'akr', 'aks', 'akt', 'aku', 'akv', 'akw', 'akx', 'aky', 'akz', 'ala', 'alc', 'ald', 'ale', 'alf', 'alg', 'alh', 'ali', 'alj', 'alk', 'all', 'alm', 'aln', 'alo', 'alp', 'alq', 'alr', 'als', 'alt', 'alu', 'alv', 'alw', 'alx', 'aly', 'alz', 'ama', 'amb', 'amc', 'ame', 'amf', 'amg', 'ami', 'amj', 'amk', 'aml', 'amm', 'amn', 'amo', 'amp', 'amq', 'amr', 'ams', 'amt', 'amu', 'amv', 'amw', 'amx', 'amy', 'amz', 'ana', 'anb', 'anc', 'and', 'ane', 'anf', 'ang', 'anh', 'ani', 'anj', 'ank', 'anl', 'anm', 'ann', 'ano', 'anp', 'anq', 'anr', 'ans', 'ant', 'anu', 'anv', 'anw', 'anx', 'any', 'anz', 'aoa', 'aob', 'aoc', 'aod', 'aoe', 'aof', 'aog', 'aoh', 'aoi', 'aoj', 'aok', 'aol', 'aom', 'aon', 'aor', 'aos', 'aot', 'aou', 'aox', 'aoz', 'apa', 'apb', 'apc', 'apd', 'ape', 'apf', 'apg', 'aph', 'api', 'apj', 'apk', 'apl', 'apm', 'apn', 'apo', 'app', 'apq', 'apr', 'aps', 'apt', 'apu', 'apv', 'apw', 'apx', 'apy', 'apz', 'aqa', 'aqc', 'aqd', 'aqg', 'aql', 'aqm', 'aqn', 'aqp', 'aqr', 'aqt', 'aqz', 'arb', 'arc', 'ard', 'are', 'arh', 'ari', 'arj', 'ark', 'arl', 'arn', 'aro', 'arp', 'arq', 'arr', 'ars', 'art', 'aru', 'arv', 'arw', 'arx', 'ary', 'arz', 'asa', 'asb', 'asc', 'asd', 'ase', 'asf', 'asg', 'ash', 'asi', 'asj', 'ask', 'asl', 'asn', 'aso', 'asp', 'asq', 'asr', 'ass', 'ast', 'asu', 'asv', 'asw', 'asx', 'asy', 'asz', 'ata', 'atb', 'atc', 'atd', 'ate', 'atg', 'ath', 'ati', 'atj', 'atk', 'atl', 'atm', 'atn', 'ato', 'atp', 'atq', 'atr', 'ats', 'att', 'atu', 'atv', 'atw', 'atx', 'aty', 'atz', 'aua', 'aub', 'auc', 'aud', 'aue', 'auf', 'aug', 'auh', 'aui', 'auj', 'auk', 'aul', 'aum', 'aun', 'auo', 'aup', 'auq', 'aur', 'aus', 'aut', 'auu', 'auw', 'aux', 'auy', 'auz', 'avb', 'avd', 'avi', 'avk', 'avl', 'avm', 'avn', 'avo', 'avs', 'avt', 'avu', 'avv', 'awa', 'awb', 'awc', 'awd', 'awe', 'awg', 'awh', 'awi', 'awk', 'awm', 'awn', 'awo', 'awr', 'aws', 'awt', 'awu', 'awv', 'aww', 'awx', 'awy', 'axb', 'axe', 'axg', 'axk', 'axl', 'axm', 'axx', 'aya', 'ayb', 'ayc', 'ayd', 'aye', 'ayg', 'ayh', 'ayi', 'ayk', 'ayl', 'ayn', 'ayo', 'ayp', 'ayq', 'ayr', 'ays', 'ayt', 'ayu', 'ayx', 'ayy', 'ayz', 'aza', 'azb', 'azc', 'azd', 'azg', 'azj', 'azm', 'azn', 'azo', 'azt', 'azz', 'baa', 'bab', 'bac', 'bad', 'bae', 'baf', 'bag', 'bah', 'bai', 'baj', 'bal', 'ban', 'bao', 'bap', 'bar', 'bas', 'bat', 'bau', 'bav', 'baw', 'bax', 'bay', 'baz', 'bba', 'bbb', 'bbc', 'bbd', 'bbe', 'bbf', 'bbg', 'bbh', 'bbi', 'bbj', 'bbk', 'bbl', 'bbm', 'bbn', 'bbo', 'bbp', 'bbq', 'bbr', 'bbs', 'bbt', 'bbu', 'bbv', 'bbw', 'bbx', 'bby', 'bbz', 'bca', 'bcb', 'bcc', 'bcd', 'bce', 'bcf', 'bcg', 'bch', 'bci', 'bcj', 'bck', 'bcl', 'bcm', 'bcn', 'bco', 'bcp', 'bcq', 'bcr', 'bcs', 'bct', 'bcu', 'bcv', 'bcw', 'bcy', 'bcz', 'bda', 'bdb', 'bdc', 'bdd', 'bde', 'bdf', 'bdg', 'bdh', 'bdi', 'bdj', 'bdk', 'bdl', 'bdm', 'bdn', 'bdo', 'bdp', 'bdq', 'bdr', 'bds', 'bdt', 'bdu', 'bdv', 'bdw', 'bdx', 'bdy', 'bdz', 'bea', 'beb', 'bec', 'bed', 'bee', 'bef', 'beg', 'beh', 'bei', 'bej', 'bek', 'bem', 'beo', 'bep', 'beq', 'ber', 'bes', 'bet', 'beu', 'bev', 'bew', 'bex', 'bey', 'bez', 'bfa', 'bfb', 'bfc', 'bfd', 'bfe', 'bff', 'bfg', 'bfh', 'bfi', 'bfj', 'bfk', 'bfl', 'bfm', 'bfn', 'bfo', 'bfp', 'bfq', 'bfr', 'bfs', 'bft', 'bfu', 'bfw', 'bfx', 'bfy', 'bfz', 'bga', 'bgb', 'bgc', 'bgd', 'bge', 'bgf', 'bgg', 'bgi', 'bgj', 'bgk', 'bgl', 'bgm', 'bgn', 'bgo', 'bgp', 'bgq', 'bgr', 'bgs', 'bgt', 'bgu', 'bgv', 'bgw', 'bgx', 'bgy', 'bgz', 'bha', 'bhb', 'bhc', 'bhd', 'bhe', 'bhf', 'bhg', 'bhh', 'bhi', 'bhj', 'bhk', 'bhl', 'bhm', 'bhn', 'bho', 'bhp', 'bhq', 'bhr', 'bhs', 'bht', 'bhu', 'bhv', 'bhw', 'bhx', 'bhy', 'bhz', 'bia', 'bib', 'bic', 'bid', 'bie', 'bif', 'big', 'bij', 'bik', 'bil', 'bim', 'bin', 'bio', 'bip', 'biq', 'bir', 'bit', 'biu', 'biv', 'biw', 'bix', 'biy', 'biz', 'bja', 'bjb', 'bjc', 'bjd', 'bje', 'bjf', 'bjg', 'bjh', 'bji', 'bjj', 'bjk', 'bjl', 'bjm', 'bjn', 'bjo', 'bjp', 'bjq', 'bjr', 'bjs', 'bjt', 'bju', 'bjv', 'bjw', 'bjx', 'bjy', 'bjz', 'bka', 'bkb', 'bkc', 'bkd', 'bkf', 'bkg', 'bkh', 'bki', 'bkj', 'bkk', 'bkl', 'bkm', 'bkn', 'bko', 'bkp', 'bkq', 'bkr', 'bks', 'bkt', 'bku', 'bkv', 'bkw', 'bkx', 'bky', 'bkz', 'bla', 'blb', 'blc', 'bld', 'ble', 'blf', 'blg', 'blh', 'bli', 'blj', 'blk', 'bll', 'blm', 'bln', 'blo', 'blp', 'blq', 'blr', 'bls', 'blt', 'blv', 'blw', 'blx', 'bly', 'blz', 'bma', 'bmb', 'bmc', 'bmd', 'bme', 'bmf', 'bmg', 'bmh', 'bmi', 'bmj', 'bmk', 'bml', 'bmm', 'bmn', 'bmo', 'bmp', 'bmq', 'bmr', 'bms', 'bmt', 'bmu', 'bmv', 'bmw', 'bmx', 'bmy', 'bmz', 'bna', 'bnb', 'bnc', 'bnd', 'bne', 'bnf', 'bng', 'bni', 'bnj', 'bnk', 'bnl', 'bnm', 'bnn', 'bno', 'bnp', 'bnq', 'bnr', 'bns', 'bnt', 'bnu', 'bnv', 'bnw', 'bnx', 'bny', 'bnz', 'boa', 'bob', 'boe', 'bof', 'bog', 'boh', 'boi', 'boj', 'bok', 'bol', 'bom', 'bon', 'boo', 'bop', 'boq', 'bor', 'bot', 'bou', 'bov', 'bow', 'box', 'boy', 'boz', 'bpa', 'bpb', 'bpd', 'bpg', 'bph', 'bpi', 'bpj', 'bpk', 'bpl', 'bpm', 'bpn', 'bpo', 'bpp', 'bpq', 'bpr', 'bps', 'bpt', 'bpu', 'bpv', 'bpw', 'bpx', 'bpy', 'bpz', 'bqa', 'bqb', 'bqc', 'bqd', 'bqf', 'bqg', 'bqh', 'bqi', 'bqj', 'bqk', 'bql', 'bqm', 'bqn', 'bqo', 'bqp', 'bqq', 'bqr', 'bqs', 'bqt', 'bqu', 'bqv', 'bqw', 'bqx', 'bqy', 'bqz', 'bra', 'brb', 'brc', 'brd', 'brf', 'brg', 'brh', 'bri', 'brj', 'brk', 'brl', 'brm', 'brn', 'bro', 'brp', 'brq', 'brr', 'brs', 'brt', 'bru', 'brv', 'brw', 'brx', 'bry', 'brz', 'bsa', 'bsb', 'bsc', 'bse', 'bsf', 'bsg', 'bsh', 'bsi', 'bsj', 'bsk', 'bsl', 'bsm', 'bsn', 'bso', 'bsp', 'bsq', 'bsr', 'bss', 'bst', 'bsu', 'bsv', 'bsw', 'bsx', 'bsy', 'bta', 'btb', 'btc', 'btd', 'bte', 'btf', 'btg', 'bth', 'bti', 'btj', 'btk', 'btl', 'btm', 'btn', 'bto', 'btp', 'btq', 'btr', 'bts', 'btt', 'btu', 'btv', 'btw', 'btx', 'bty', 'btz', 'bua', 'bub', 'buc', 'bud', 'bue', 'buf', 'bug', 'buh', 'bui', 'buj', 'buk', 'bum', 'bun', 'buo', 'bup', 'buq', 'bus', 'but', 'buu', 'buv', 'buw', 'bux', 'buy', 'buz', 'bva', 'bvb', 'bvc', 'bvd', 'bve', 'bvf', 'bvg', 'bvh', 'bvi', 'bvj', 'bvk', 'bvl', 'bvm', 'bvn', 'bvo', 'bvp', 'bvq', 'bvr', 'bvt', 'bvu', 'bvv', 'bvw', 'bvx', 'bvy', 'bvz', 'bwa', 'bwb', 'bwc', 'bwd', 'bwe', 'bwf', 'bwg', 'bwh', 'bwi', 'bwj', 'bwk', 'bwl', 'bwm', 'bwn', 'bwo', 'bwp', 'bwq', 'bwr', 'bws', 'bwt', 'bwu', 'bww', 'bwx', 'bwy', 'bwz', 'bxa', 'bxb', 'bxc', 'bxd', 'bxe', 'bxf', 'bxg', 'bxh', 'bxi', 'bxj', 'bxk', 'bxl', 'bxm', 'bxn', 'bxo', 'bxp', 'bxq', 'bxr', 'bxs', 'bxu', 'bxv', 'bxw', 'bxx', 'bxz', 'bya', 'byb', 'byc', 'byd', 'bye', 'byf', 'byg', 'byh', 'byi', 'byj', 'byk', 'byl', 'bym', 'byn', 'byo', 'byp', 'byq', 'byr', 'bys', 'byt', 'byv', 'byw', 'byx', 'byy', 'byz', 'bza', 'bzb', 'bzc', 'bzd', 'bze', 'bzf', 'bzg', 'bzh', 'bzi', 'bzj', 'bzk', 'bzl', 'bzm', 'bzn', 'bzo', 'bzp', 'bzq', 'bzr', 'bzs', 'bzt', 'bzu', 'bzv', 'bzw', 'bzx', 'bzy', 'bzz', 'caa', 'cab', 'cac', 'cad', 'cae', 'caf', 'cag', 'cah', 'cai', 'caj', 'cak', 'cal', 'cam', 'can', 'cao', 'cap', 'caq', 'car', 'cas', 'cau', 'cav', 'caw', 'cax', 'cay', 'caz', 'cba', 'cbb', 'cbc', 'cbd', 'cbe', 'cbg', 'cbh', 'cbi', 'cbj', 'cbk', 'cbl', 'cbn', 'cbo', 'cbq', 'cbr', 'cbs', 'cbt', 'cbu', 'cbv', 'cbw', 'cby', 'cca', 'ccc', 'ccd', 'cce', 'ccg', 'cch', 'ccj', 'ccl', 'ccm', 'ccn', 'cco', 'ccp', 'ccq', 'ccr', 'ccs', 'cda', 'cdc', 'cdd', 'cde', 'cdf', 'cdg', 'cdh', 'cdi', 'cdj', 'cdm', 'cdn', 'cdo', 'cdr', 'cds', 'cdy', 'cdz', 'cea', 'ceb', 'ceg', 'cek', 'cel', 'cen', 'cet', 'cfa', 'cfd', 'cfg', 'cfm', 'cga', 'cgc', 'cgg', 'cgk', 'chb', 'chc', 'chd', 'chf', 'chg', 'chh', 'chj', 'chk', 'chl', 'chm', 'chn', 'cho', 'chp', 'chq', 'chr', 'cht', 'chw', 'chx', 'chy', 'chz', 'cia', 'cib', 'cic', 'cid', 'cie', 'cih', 'cik', 'cim', 'cin', 'cip', 'cir', 'ciw', 'ciy', 'cja', 'cje', 'cjh', 'cji', 'cjk', 'cjm', 'cjn', 'cjo', 'cjp', 'cjr', 'cjs', 'cjv', 'cjy', 'cka', 'ckb', 'ckh', 'ckl', 'ckn', 'cko', 'ckq', 'ckr', 'cks', 'ckt', 'cku', 'ckv', 'ckx', 'cky', 'ckz', 'cla', 'clc', 'cld', 'cle', 'clh', 'cli', 'clj', 'clk', 'cll', 'clm', 'clo', 'clt', 'clu', 'clw', 'cly', 'cma', 'cmc', 'cme', 'cmg', 'cmi', 'cmk', 'cml', 'cmm', 'cmn', 'cmo', 'cmr', 'cms', 'cmt', 'cna', 'cnb', 'cnc', 'cng', 'cnh', 'cni', 'cnk', 'cnl', 'cno', 'cnr', 'cns', 'cnt', 'cnu', 'cnw', 'cnx', 'coa', 'cob', 'coc', 'cod', 'coe', 'cof', 'cog', 'coh', 'coj', 'cok', 'col', 'com', 'con', 'coo', 'cop', 'coq', 'cot', 'cou', 'cov', 'cow', 'cox', 'coy', 'coz', 'cpa', 'cpb', 'cpc', 'cpe', 'cpf', 'cpg', 'cpi', 'cpn', 'cpo', 'cpp', 'cps', 'cpu', 'cpx', 'cpy', 'cqd', 'cqu', 'cra', 'crb', 'crc', 'crd', 'crf', 'crg', 'crh', 'cri', 'crj', 'crk', 'crl', 'crm', 'crn', 'cro', 'crp', 'crq', 'crr', 'crs', 'crt', 'crv', 'crw', 'crx', 'cry', 'crz', 'csa', 'csb', 'csc', 'csd', 'cse', 'csf', 'csg', 'csh', 'csi', 'csj', 'csk', 'csl', 'csm', 'csn', 'cso', 'csq', 'csr', 'css', 'cst', 'csu', 'csv', 'csw', 'csy', 'csz', 'cta', 'ctc', 'ctd', 'cte', 'ctg', 'cth', 'ctl', 'ctm', 'ctn', 'cto', 'ctp', 'cts', 'ctt', 'ctu', 'ctz', 'cua', 'cub', 'cuc', 'cug', 'cuh', 'cui', 'cuj', 'cuk', 'cul', 'cum', 'cuo', 'cup', 'cuq', 'cur', 'cus', 'cut', 'cuu', 'cuv', 'cuw', 'cux', 'cuy', 'cvg', 'cvn', 'cwa', 'cwb', 'cwd', 'cwe', 'cwg', 'cwt', 'cya', 'cyb', 'cyo', 'czh', 'czk', 'czn', 'czo', 'czt', 'daa', 'dac', 'dad', 'dae', 'daf', 'dag', 'dah', 'dai', 'daj', 'dak', 'dal', 'dam', 'dao', 'dap', 'daq', 'dar', 'das', 'dau', 'dav', 'daw', 'dax', 'day', 'daz', 'dba', 'dbb', 'dbd', 'dbe', 'dbf', 'dbg', 'dbi', 'dbj', 'dbl', 'dbm', 'dbn', 'dbo', 'dbp', 'dbq', 'dbr', 'dbt', 'dbu', 'dbv', 'dbw', 'dby', 'dcc', 'dcr', 'dda', 'ddd', 'dde', 'ddg', 'ddi', 'ddj', 'ddn', 'ddo', 'ddr', 'dds', 'ddw', 'dec', 'ded', 'dee', 'def', 'deg', 'deh', 'dei', 'dek', 'del', 'dem', 'den', 'dep', 'deq', 'der', 'des', 'dev', 'dez', 'dga', 'dgb', 'dgc', 'dgd', 'dge', 'dgg', 'dgh', 'dgi', 'dgk', 'dgl', 'dgn', 'dgo', 'dgr', 'dgs', 'dgt', 'dgu', 'dgw', 'dgx', 'dgz', 'dha', 'dhd', 'dhg', 'dhi', 'dhl', 'dhm', 'dhn', 'dho', 'dhr', 'dhs', 'dhu', 'dhv', 'dhw', 'dhx', 'dia', 'dib', 'dic', 'did', 'dif', 'dig', 'dih', 'dii', 'dij', 'dik', 'dil', 'dim', 'din', 'dio', 'dip', 'diq', 'dir', 'dis', 'dit', 'diu', 'diw', 'dix', 'diy', 'diz', 'dja', 'djb', 'djc', 'djd', 'dje', 'djf', 'dji', 'djj', 'djk', 'djl', 'djm', 'djn', 'djo', 'djr', 'dju', 'djw', 'dka', 'dkk', 'dkl', 'dkr', 'dks', 'dkx', 'dlg', 'dlk', 'dlm', 'dln', 'dma', 'dmb', 'dmc', 'dmd', 'dme', 'dmg', 'dmk', 'dml', 'dmm', 'dmn', 'dmo', 'dmr', 'dms', 'dmu', 'dmv', 'dmw', 'dmx', 'dmy', 'dna', 'dnd', 'dne', 'dng', 'dni', 'dnj', 'dnk', 'dnn', 'dnr', 'dnt', 'dnu', 'dnv', 'dnw', 'dny', 'doa', 'dob', 'doc', 'doe', 'dof', 'doh', 'doi', 'dok', 'dol', 'don', 'doo', 'dop', 'doq', 'dor', 'dos', 'dot', 'dov', 'dow', 'dox', 'doy', 'doz', 'dpp', 'dra', 'drb', 'drc', 'drd', 'dre', 'drg', 'drh', 'dri', 'drl', 'drn', 'dro', 'drq', 'drr', 'drs', 'drt', 'dru', 'drw', 'dry', 'dsb', 'dse', 'dsh', 'dsi', 'dsl', 'dsn', 'dso', 'dsq', 'dta', 'dtb', 'dtd', 'dth', 'dti', 'dtk', 'dtm', 'dtn', 'dto', 'dtp', 'dtr', 'dts', 'dtt', 'dtu', 'dty', 'dua', 'dub', 'duc', 'dud', 'due', 'duf', 'dug', 'duh', 'dui', 'duj', 'duk', 'dul', 'dum', 'dun', 'duo', 'dup', 'duq', 'dur', 'dus', 'duu', 'duv', 'duw', 'dux', 'duy', 'duz', 'dva', 'dwa', 'dwl', 'dwr', 'dws', 'dwu', 'dww', 'dwy', 'dya', 'dyb', 'dyd', 'dyg', 'dyi', 'dym', 'dyn', 'dyo', 'dyu', 'dyy', 'dza', 'dzd', 'dze', 'dzg', 'dzl', 'dzn', 'eaa', 'ebg', 'ebk', 'ebo', 'ebr', 'ebu', 'ecr', 'ecs', 'ecy', 'eee', 'efa', 'efe', 'efi', 'ega', 'egl', 'ego', 'egx', 'egy', 'ehu', 'eip', 'eit', 'eiv', 'eja', 'eka', 'ekc', 'eke', 'ekg', 'eki', 'ekk', 'ekl', 'ekm', 'eko', 'ekp', 'ekr', 'eky', 'ele', 'elh', 'eli', 'elk', 'elm', 'elo', 'elp', 'elu', 'elx', 'ema', 'emb', 'eme', 'emg', 'emi', 'emk', 'emm', 'emn', 'emo', 'emp', 'ems', 'emu', 'emw', 'emx', 'emy', 'ena', 'enb', 'enc', 'end', 'enf', 'enh', 'enl', 'enm', 'enn', 'eno', 'enq', 'enr', 'enu', 'env', 'enw', 'enx', 'eot', 'epi', 'era', 'erg', 'erh', 'eri', 'erk', 'ero', 'err', 'ers', 'ert', 'erw', 'ese', 'esg', 'esh', 'esi', 'esk', 'esl', 'esm', 'esn', 'eso', 'esq', 'ess', 'esu', 'esx', 'esy', 'etb', 'etc', 'eth', 'etn', 'eto', 'etr', 'ets', 'ett', 'etu', 'etx', 'etz', 'euq', 'eve', 'evh', 'evn', 'ewo', 'ext', 'eya', 'eyo', 'eza', 'eze', 'faa', 'fab', 'fad', 'faf', 'fag', 'fah', 'fai', 'faj', 'fak', 'fal', 'fam', 'fan', 'fap', 'far', 'fat', 'fau', 'fax', 'fay', 'faz', 'fbl', 'fcs', 'fer', 'ffi', 'ffm', 'fgr', 'fia', 'fie', 'fil', 'fip', 'fir', 'fit', 'fiu', 'fiw', 'fkk', 'fkv', 'fla', 'flh', 'fli', 'fll', 'fln', 'flr', 'fly', 'fmp', 'fmu', 'fnb', 'fng', 'fni', 'fod', 'foi', 'fom', 'fon', 'for', 'fos', 'fox', 'fpe', 'fqs', 'frc', 'frd', 'frk', 'frm', 'fro', 'frp', 'frq', 'frr', 'frs', 'frt', 'fse', 'fsl', 'fss', 'fub', 'fuc', 'fud', 'fue', 'fuf', 'fuh', 'fui', 'fuj', 'fum', 'fun', 'fuq', 'fur', 'fut', 'fuu', 'fuv', 'fuy', 'fvr', 'fwa', 'fwe', 'gaa', 'gab', 'gac', 'gad', 'gae', 'gaf', 'gag', 'gah', 'gai', 'gaj', 'gak', 'gal', 'gam', 'gan', 'gao', 'gap', 'gaq', 'gar', 'gas', 'gat', 'gau', 'gav', 'gaw', 'gax', 'gay', 'gaz', 'gba', 'gbb', 'gbc', 'gbd', 'gbe', 'gbf', 'gbg', 'gbh', 'gbi', 'gbj', 'gbk', 'gbl', 'gbm', 'gbn', 'gbo', 'gbp', 'gbq', 'gbr', 'gbs', 'gbu', 'gbv', 'gbw', 'gbx', 'gby', 'gbz', 'gcc', 'gcd', 'gce', 'gcf', 'gcl', 'gcn', 'gcr', 'gct', 'gda', 'gdb', 'gdc', 'gdd', 'gde', 'gdf', 'gdg', 'gdh', 'gdi', 'gdj', 'gdk', 'gdl', 'gdm', 'gdn', 'gdo', 'gdq', 'gdr', 'gds', 'gdt', 'gdu', 'gdx', 'gea', 'geb', 'gec', 'ged', 'geg', 'geh', 'gei', 'gej', 'gek', 'gel', 'gem', 'geq', 'ges', 'gev', 'gew', 'gex', 'gey', 'gez', 'gfk', 'gft', 'gfx', 'gga', 'ggb', 'ggd', 'gge', 'ggg', 'ggk', 'ggl', 'ggn', 'ggo', 'ggr', 'ggt', 'ggu', 'ggw', 'gha', 'ghc', 'ghe', 'ghh', 'ghk', 'ghl', 'ghn', 'gho', 'ghr', 'ghs', 'ght', 'gia', 'gib', 'gic', 'gid', 'gie', 'gig', 'gih', 'gil', 'gim', 'gin', 'gio', 'gip', 'giq', 'gir', 'gis', 'git', 'giu', 'giw', 'gix', 'giy', 'giz', 'gji', 'gjk', 'gjm', 'gjn', 'gjr', 'gju', 'gka', 'gkd', 'gke', 'gkn', 'gko', 'gkp', 'gku', 'glc', 'gld', 'glh', 'gli', 'glj', 'glk', 'gll', 'glo', 'glr', 'glu', 'glw', 'gly', 'gma', 'gmb', 'gmd', 'gme', 'gmg', 'gmh', 'gml', 'gmm', 'gmn', 'gmq', 'gmu', 'gmv', 'gmw', 'gmx', 'gmy', 'gmz', 'gna', 'gnb', 'gnc', 'gnd', 'gne', 'gng', 'gnh', 'gni', 'gnj', 'gnk', 'gnl', 'gnm', 'gnn', 'gno', 'gnq', 'gnr', 'gnt', 'gnu', 'gnw', 'gnz', 'goa', 'gob', 'goc', 'god', 'goe', 'gof', 'gog', 'goh', 'goi', 'goj', 'gok', 'gol', 'gom', 'gon', 'goo', 'gop', 'goq', 'gor', 'gos', 'got', 'gou', 'gow', 'gox', 'goy', 'goz', 'gpa', 'gpe', 'gpn', 'gqa', 'gqi', 'gqn', 'gqr', 'gqu', 'gra', 'grb', 'grc', 'grd', 'grg', 'grh', 'gri', 'grj', 'grk', 'grm', 'gro', 'grq', 'grr', 'grs', 'grt', 'gru', 'grv', 'grw', 'grx', 'gry', 'grz', 'gse', 'gsg', 'gsl', 'gsm', 'gsn', 'gso', 'gsp', 'gss', 'gsw', 'gta', 'gti', 'gtu', 'gua', 'gub', 'guc', 'gud', 'gue', 'guf', 'gug', 'guh', 'gui', 'guk', 'gul', 'gum', 'gun', 'guo', 'gup', 'guq', 'gur', 'gus', 'gut', 'guu', 'guv', 'guw', 'gux', 'guz', 'gva', 'gvc', 'gve', 'gvf', 'gvj', 'gvl', 'gvm', 'gvn', 'gvo', 'gvp', 'gvr', 'gvs', 'gvy', 'gwa', 'gwb', 'gwc', 'gwd', 'gwe', 'gwf', 'gwg', 'gwi', 'gwj', 'gwm', 'gwn', 'gwr', 'gwt', 'gwu', 'gww', 'gwx', 'gxx', 'gya', 'gyb', 'gyd', 'gye', 'gyf', 'gyg', 'gyi', 'gyl', 'gym', 'gyn', 'gyo', 'gyr', 'gyy', 'gza', 'gzi', 'gzn', 'haa', 'hab', 'hac', 'had', 'hae', 'haf', 'hag', 'hah', 'hai', 'haj', 'hak', 'hal', 'ham', 'han', 'hao', 'hap', 'haq', 'har', 'has', 'hav', 'haw', 'hax', 'hay', 'haz', 'hba', 'hbb', 'hbn', 'hbo', 'hbu', 'hca', 'hch', 'hdn', 'hds', 'hdy', 'hea', 'hed', 'heg', 'heh', 'hei', 'hem', 'hgm', 'hgw', 'hhi', 'hhr', 'hhy', 'hia', 'hib', 'hid', 'hif', 'hig', 'hih', 'hii', 'hij', 'hik', 'hil', 'him', 'hio', 'hir', 'hit', 'hiw', 'hix', 'hji', 'hka', 'hke', 'hkk', 'hkn', 'hks', 'hla', 'hlb', 'hld', 'hle', 'hlt', 'hlu', 'hma', 'hmb', 'hmc', 'hmd', 'hme', 'hmf', 'hmg', 'hmh', 'hmi', 'hmj', 'hmk', 'hml', 'hmm', 'hmn', 'hmp', 'hmq', 'hmr', 'hms', 'hmt', 'hmu', 'hmv', 'hmw', 'hmx', 'hmy', 'hmz', 'hna', 'hnd', 'hne', 'hnh', 'hni', 'hnj', 'hnn', 'hno', 'hns', 'hnu', 'hoa', 'hob', 'hoc', 'hod', 'hoe', 'hoh', 'hoi', 'hoj', 'hok', 'hol', 'hom', 'hoo', 'hop', 'hor', 'hos', 'hot', 'hov', 'how', 'hoy', 'hoz', 'hpo', 'hps', 'hra', 'hrc', 'hre', 'hrk', 'hrm', 'hro', 'hrp', 'hrr', 'hrt', 'hru', 'hrw', 'hrx', 'hrz', 'hsb', 'hsh', 'hsl', 'hsn', 'hss', 'hti', 'hto', 'hts', 'htu', 'htx', 'hub', 'huc', 'hud', 'hue', 'huf', 'hug', 'huh', 'hui', 'huj', 'huk', 'hul', 'hum', 'huo', 'hup', 'huq', 'hur', 'hus', 'hut', 'huu', 'huv', 'huw', 'hux', 'huy', 'huz', 'hvc', 'hve', 'hvk', 'hvn', 'hvv', 'hwa', 'hwc', 'hwo', 'hya', 'hyw', 'hyx', 'iai', 'ian', 'iap', 'iar', 'iba', 'ibb', 'ibd', 'ibe', 'ibg', 'ibh', 'ibi', 'ibl', 'ibm', 'ibn', 'ibr', 'ibu', 'iby', 'ica', 'ich', 'icl', 'icr', 'ida', 'idb', 'idc', 'idd', 'ide', 'idi', 'idr', 'ids', 'idt', 'idu', 'ifa', 'ifb', 'ife', 'iff', 'ifk', 'ifm', 'ifu', 'ify', 'igb', 'ige', 'igg', 'igl', 'igm', 'ign', 'igo', 'igs', 'igw', 'ihb', 'ihi', 'ihp', 'ihw', 'iin', 'iir', 'ijc', 'ije', 'ijj', 'ijn', 'ijo', 'ijs', 'ike', 'iki', 'ikk', 'ikl', 'iko', 'ikp', 'ikr', 'iks', 'ikt', 'ikv', 'ikw', 'ikx', 'ikz', 'ila', 'ilb', 'ilg', 'ili', 'ilk', 'ill', 'ilm', 'ilo', 'ilp', 'ils', 'ilu', 'ilv', 'ilw', 'ima', 'ime', 'imi', 'iml', 'imn', 'imo', 'imr', 'ims', 'imy', 'inb', 'inc', 'ine', 'ing', 'inh', 'inj', 'inl', 'inm', 'inn', 'ino', 'inp', 'ins', 'int', 'inz', 'ior', 'iou', 'iow', 'ipi', 'ipo', 'iqu', 'iqw', 'ira', 'ire', 'irh', 'iri', 'irk', 'irn', 'iro', 'irr', 'iru', 'irx', 'iry', 'isa', 'isc', 'isd', 'ise', 'isg', 'ish', 'isi', 'isk', 'ism', 'isn', 'iso', 'isr', 'ist', 'isu', 'itb', 'itc', 'itd', 'ite', 'iti', 'itk', 'itl', 'itm', 'ito', 'itr', 'its', 'itt', 'itv', 'itw', 'itx', 'ity', 'itz', 'ium', 'ivb', 'ivv', 'iwk', 'iwm', 'iwo', 'iws', 'ixc', 'ixl', 'iya', 'iyo', 'iyx', 'izh', 'izi', 'izr', 'izz', 'jaa', 'jab', 'jac', 'jad', 'jae', 'jaf', 'jah', 'jaj', 'jak', 'jal', 'jam', 'jan', 'jao', 'jaq', 'jar', 'jas', 'jat', 'jau', 'jax', 'jay', 'jaz', 'jbe', 'jbi', 'jbj', 'jbk', 'jbn', 'jbo', 'jbr', 'jbt', 'jbu', 'jbw', 'jcs', 'jct', 'jda', 'jdg', 'jdt', 'jeb', 'jee', 'jeg', 'jeh', 'jei', 'jek', 'jel', 'jen', 'jer', 'jet', 'jeu', 'jgb', 'jge', 'jgk', 'jgo', 'jhi', 'jhs', 'jia', 'jib', 'jic', 'jid', 'jie', 'jig', 'jih', 'jii', 'jil', 'jim', 'jio', 'jiq', 'jit', 'jiu', 'jiv', 'jiy', 'jje', 'jjr', 'jka', 'jkm', 'jko', 'jkp', 'jkr', 'jku', 'jle', 'jls', 'jma', 'jmb', 'jmc', 'jmd', 'jmi', 'jml', 'jmn', 'jmr', 'jms', 'jmw', 'jmx', 'jna', 'jnd', 'jng', 'jni', 'jnj', 'jnl', 'jns', 'job', 'jod', 'jog', 'jor', 'jos', 'jow', 'jpa', 'jpr', 'jpx', 'jqr', 'jra', 'jrb', 'jrr', 'jrt', 'jru', 'jsl', 'jua', 'jub', 'juc', 'jud', 'juh', 'jui', 'juk', 'jul', 'jum', 'jun', 'juo', 'jup', 'jur', 'jus', 'jut', 'juu', 'juw', 'juy', 'jvd', 'jvn', 'jwi', 'jya', 'jye', 'jyy', 'kaa', 'kab', 'kac', 'kad', 'kae', 'kaf', 'kag', 'kah', 'kai', 'kaj', 'kak', 'kam', 'kao', 'kap', 'kaq', 'kar', 'kav', 'kaw', 'kax', 'kay', 'kba', 'kbb', 'kbc', 'kbd', 'kbe', 'kbf', 'kbg', 'kbh', 'kbi', 'kbj', 'kbk', 'kbl', 'kbm', 'kbn', 'kbo', 'kbp', 'kbq', 'kbr', 'kbs', 'kbt', 'kbu', 'kbv', 'kbw', 'kbx', 'kby', 'kbz', 'kca', 'kcb', 'kcc', 'kcd', 'kce', 'kcf', 'kcg', 'kch', 'kci', 'kcj', 'kck', 'kcl', 'kcm', 'kcn', 'kco', 'kcp', 'kcq', 'kcr', 'kcs', 'kct', 'kcu', 'kcv', 'kcw', 'kcx', 'kcy', 'kcz', 'kda', 'kdc', 'kdd', 'kde', 'kdf', 'kdg', 'kdh', 'kdi', 'kdj', 'kdk', 'kdl', 'kdm', 'kdn', 'kdo', 'kdp', 'kdq', 'kdr', 'kdt', 'kdu', 'kdv', 'kdw', 'kdx', 'kdy', 'kdz', 'kea', 'keb', 'kec', 'ked', 'kee', 'kef', 'keg', 'keh', 'kei', 'kej', 'kek', 'kel', 'kem', 'ken', 'keo', 'kep', 'keq', 'ker', 'kes', 'ket', 'keu', 'kev', 'kew', 'kex', 'key', 'kez', 'kfa', 'kfb', 'kfc', 'kfd', 'kfe', 'kff', 'kfg', 'kfh', 'kfi', 'kfj', 'kfk', 'kfl', 'kfm', 'kfn', 'kfo', 'kfp', 'kfq', 'kfr', 'kfs', 'kft', 'kfu', 'kfv', 'kfw', 'kfx', 'kfy', 'kfz', 'kga', 'kgb', 'kgc', 'kgd', 'kge', 'kgf', 'kgg', 'kgh', 'kgi', 'kgj', 'kgk', 'kgl', 'kgm', 'kgn', 'kgo', 'kgp', 'kgq', 'kgr', 'kgs', 'kgt', 'kgu', 'kgv', 'kgw', 'kgx', 'kgy', 'kha', 'khb', 'khc', 'khd', 'khe', 'khf', 'khg', 'khh', 'khi', 'khj', 'khk', 'khl', 'khn', 'kho', 'khp', 'khq', 'khr', 'khs', 'kht', 'khu', 'khv', 'khw', 'khx', 'khy', 'khz', 'kia', 'kib', 'kic', 'kid', 'kie', 'kif', 'kig', 'kih', 'kii', 'kij', 'kil', 'kim', 'kio', 'kip', 'kiq', 'kis', 'kit', 'kiu', 'kiv', 'kiw', 'kix', 'kiy', 'kiz', 'kja', 'kjb', 'kjc', 'kjd', 'kje', 'kjf', 'kjg', 'kjh', 'kji', 'kjj', 'kjk', 'kjl', 'kjm', 'kjn', 'kjo', 'kjp', 'kjq', 'kjr', 'kjs', 'kjt', 'kju', 'kjv', 'kjx', 'kjy', 'kjz', 'kka', 'kkb', 'kkc', 'kkd', 'kke', 'kkf', 'kkg', 'kkh', 'kki', 'kkj', 'kkk', 'kkl', 'kkm', 'kkn', 'kko', 'kkp', 'kkq', 'kkr', 'kks', 'kkt', 'kku', 'kkv', 'kkw', 'kkx', 'kky', 'kkz', 'kla', 'klb', 'klc', 'kld', 'kle', 'klf', 'klg', 'klh', 'kli', 'klj', 'klk', 'kll', 'klm', 'kln', 'klo', 'klp', 'klq', 'klr', 'kls', 'klt', 'klu', 'klv', 'klw', 'klx', 'kly', 'klz', 'kma', 'kmb', 'kmc', 'kmd', 'kme', 'kmf', 'kmg', 'kmh', 'kmi', 'kmj', 'kmk', 'kml', 'kmm', 'kmn', 'kmo', 'kmp', 'kmq', 'kmr', 'kms', 'kmt', 'kmu', 'kmv', 'kmw', 'kmx', 'kmy', 'kmz', 'kna', 'knb', 'knc', 'knd', 'kne', 'knf', 'kng', 'kni', 'knj', 'knk', 'knl', 'knm', 'knn', 'kno', 'knp', 'knq', 'knr', 'kns', 'knt', 'knu', 'knv', 'knw', 'knx', 'kny', 'knz', 'koa', 'koc', 'kod', 'koe', 'kof', 'kog', 'koh', 'koi', 'koj', 'kok', 'kol', 'koo', 'kop', 'koq', 'kos', 'kot', 'kou', 'kov', 'kow', 'kox', 'koy', 'koz', 'kpa', 'kpb', 'kpc', 'kpd', 'kpe', 'kpf', 'kpg', 'kph', 'kpi', 'kpj', 'kpk', 'kpl', 'kpm', 'kpn', 'kpo', 'kpp', 'kpq', 'kpr', 'kps', 'kpt', 'kpu', 'kpv', 'kpw', 'kpx', 'kpy', 'kpz', 'kqa', 'kqb', 'kqc', 'kqd', 'kqe', 'kqf', 'kqg', 'kqh', 'kqi', 'kqj', 'kqk', 'kql', 'kqm', 'kqn', 'kqo', 'kqp', 'kqq', 'kqr', 'kqs', 'kqt', 'kqu', 'kqv', 'kqw', 'kqx', 'kqy', 'kqz', 'kra', 'krb', 'krc', 'krd', 'kre', 'krf', 'krh', 'kri', 'krj', 'krk', 'krl', 'krm', 'krn', 'kro', 'krp', 'krr', 'krs', 'krt', 'kru', 'krv', 'krw', 'krx', 'kry', 'krz', 'ksa', 'ksb', 'ksc', 'ksd', 'kse', 'ksf', 'ksg', 'ksh', 'ksi', 'ksj', 'ksk', 'ksl', 'ksm', 'ksn', 'kso', 'ksp', 'ksq', 'ksr', 'kss', 'kst', 'ksu', 'ksv', 'ksw', 'ksx', 'ksy', 'ksz', 'kta', 'ktb', 'ktc', 'ktd', 'kte', 'ktf', 'ktg', 'kth', 'kti', 'ktj', 'ktk', 'ktl', 'ktm', 'ktn', 'kto', 'ktp', 'ktq', 'ktr', 'kts', 'ktt', 'ktu', 'ktv', 'ktw', 'ktx', 'kty', 'ktz', 'kub', 'kuc', 'kud', 'kue', 'kuf', 'kug', 'kuh', 'kui', 'kuj', 'kuk', 'kul', 'kum', 'kun', 'kuo', 'kup', 'kuq', 'kus', 'kut', 'kuu', 'kuv', 'kuw', 'kux', 'kuy', 'kuz', 'kva', 'kvb', 'kvc', 'kvd', 'kve', 'kvf', 'kvg', 'kvh', 'kvi', 'kvj', 'kvk', 'kvl', 'kvm', 'kvn', 'kvo', 'kvp', 'kvq', 'kvr', 'kvs', 'kvt', 'kvu', 'kvv', 'kvw', 'kvx', 'kvy', 'kvz', 'kwa', 'kwb', 'kwc', 'kwd', 'kwe', 'kwf', 'kwg', 'kwh', 'kwi', 'kwj', 'kwk', 'kwl', 'kwm', 'kwn', 'kwo', 'kwp', 'kwq', 'kwr', 'kws', 'kwt', 'kwu', 'kwv', 'kww', 'kwx', 'kwy', 'kwz', 'kxa', 'kxb', 'kxc', 'kxd', 'kxe', 'kxf', 'kxh', 'kxi', 'kxj', 'kxk', 'kxl', 'kxm', 'kxn', 'kxo', 'kxp', 'kxq', 'kxr', 'kxs', 'kxt', 'kxu', 'kxv', 'kxw', 'kxx', 'kxy', 'kxz', 'kya', 'kyb', 'kyc', 'kyd', 'kye', 'kyf', 'kyg', 'kyh', 'kyi', 'kyj', 'kyk', 'kyl', 'kym', 'kyn', 'kyo', 'kyp', 'kyq', 'kyr', 'kys', 'kyt', 'kyu', 'kyv', 'kyw', 'kyx', 'kyy', 'kyz', 'kza', 'kzb', 'kzc', 'kzd', 'kze', 'kzf', 'kzg', 'kzh', 'kzi', 'kzj', 'kzk', 'kzl', 'kzm', 'kzn', 'kzo', 'kzp', 'kzq', 'kzr', 'kzs', 'kzt', 'kzu', 'kzv', 'kzw', 'kzx', 'kzy', 'kzz', 'laa', 'lab', 'lac', 'lad', 'lae', 'laf', 'lag', 'lah', 'lai', 'laj', 'lak', 'lal', 'lam', 'lan', 'lap', 'laq', 'lar', 'las', 'lau', 'law', 'lax', 'lay', 'laz', 'lba', 'lbb', 'lbc', 'lbe', 'lbf', 'lbg', 'lbi', 'lbj', 'lbk', 'lbl', 'lbm', 'lbn', 'lbo', 'lbq', 'lbr', 'lbs', 'lbt', 'lbu', 'lbv', 'lbw', 'lbx', 'lby', 'lbz', 'lcc', 'lcd', 'lce', 'lcf', 'lch', 'lcl', 'lcm', 'lcp', 'lcq', 'lcs', 'lda', 'ldb', 'ldd', 'ldg', 'ldh', 'ldi', 'ldj', 'ldk', 'ldl', 'ldm', 'ldn', 'ldo', 'ldp', 'ldq', 'lea', 'leb', 'lec', 'led', 'lee', 'lef', 'leg', 'leh', 'lei', 'lej', 'lek', 'lel', 'lem', 'len', 'leo', 'lep', 'leq', 'ler', 'les', 'let', 'leu', 'lev', 'lew', 'lex', 'ley', 'lez', 'lfa', 'lfn', 'lga', 'lgb', 'lgg', 'lgh', 'lgi', 'lgk', 'lgl', 'lgm', 'lgn', 'lgq', 'lgr', 'lgt', 'lgu', 'lgz', 'lha', 'lhh', 'lhi', 'lhl', 'lhm', 'lhn', 'lhp', 'lhs', 'lht', 'lhu', 'lia', 'lib', 'lic', 'lid', 'lie', 'lif', 'lig', 'lih', 'lii', 'lij', 'lik', 'lil', 'lio', 'lip', 'liq', 'lir', 'lis', 'liu', 'liv', 'liw', 'lix', 'liy', 'liz', 'lja', 'lje', 'lji', 'ljl', 'ljp', 'ljw', 'ljx', 'lka', 'lkb', 'lkc', 'lkd', 'lke', 'lkh', 'lki', 'lkj', 'lkl', 'lkm', 'lkn', 'lko', 'lkr', 'lks', 'lkt', 'lku', 'lky', 'lla', 'llb', 'llc', 'lld', 'lle', 'llf', 'llg', 'llh', 'lli', 'llj', 'llk', 'lll', 'llm', 'lln', 'llo', 'llp', 'llq', 'lls', 'llu', 'llx', 'lma', 'lmb', 'lmc', 'lmd', 'lme', 'lmf', 'lmg', 'lmh', 'lmi', 'lmj', 'lmk', 'lml', 'lmm', 'lmn', 'lmo', 'lmp', 'lmq', 'lmr', 'lmu', 'lmv', 'lmw', 'lmx', 'lmy', 'lmz', 'lna', 'lnb', 'lnd', 'lng', 'lnh', 'lni', 'lnj', 'lnl', 'lnm', 'lnn', 'lno', 'lns', 'lnu', 'lnw', 'lnz', 'loa', 'lob', 'loc', 'loe', 'lof', 'log', 'loh', 'loi', 'loj', 'lok', 'lol', 'lom', 'lon', 'loo', 'lop', 'loq', 'lor', 'los', 'lot', 'lou', 'lov', 'low', 'lox', 'loy', 'loz', 'lpa', 'lpe', 'lpn', 'lpo', 'lpx', 'lra', 'lrc', 'lre', 'lrg', 'lri', 'lrk', 'lrl', 'lrm', 'lrn', 'lro', 'lrr', 'lrt', 'lrv', 'lrz', 'lsa', 'lsd', 'lse', 'lsg', 'lsh', 'lsi', 'lsl', 'lsm', 'lso', 'lsp', 'lsr', 'lss', 'lst', 'lsy', 'ltc', 'ltg', 'lth', 'lti', 'ltn', 'lto', 'lts', 'ltu', 'lua', 'luc', 'lud', 'lue', 'luf', 'lui', 'luj', 'luk', 'lul', 'lum', 'lun', 'luo', 'lup', 'luq', 'lur', 'lus', 'lut', 'luu', 'luv', 'luw', 'luy', 'luz', 'lva', 'lvk', 'lvs', 'lvu', 'lwa', 'lwe', 'lwg', 'lwh', 'lwl', 'lwm', 'lwo', 'lws', 'lwt', 'lwu', 'lww', 'lya', 'lyg', 'lyn', 'lzh', 'lzl', 'lzn', 'lzz', 'maa', 'mab', 'mad', 'mae', 'maf', 'mag', 'mai', 'maj', 'mak', 'mam', 'man', 'map', 'maq', 'mas', 'mat', 'mau', 'mav', 'maw', 'max', 'maz', 'mba', 'mbb', 'mbc', 'mbd', 'mbe', 'mbf', 'mbh', 'mbi', 'mbj', 'mbk', 'mbl', 'mbm', 'mbn', 'mbo', 'mbp', 'mbq', 'mbr', 'mbs', 'mbt', 'mbu', 'mbv', 'mbw', 'mbx', 'mby', 'mbz', 'mca', 'mcb', 'mcc', 'mcd', 'mce', 'mcf', 'mcg', 'mch', 'mci', 'mcj', 'mck', 'mcl', 'mcm', 'mcn', 'mco', 'mcp', 'mcq', 'mcr', 'mcs', 'mct', 'mcu', 'mcv', 'mcw', 'mcx', 'mcy', 'mcz', 'mda', 'mdb', 'mdc', 'mdd', 'mde', 'mdf', 'mdg', 'mdh', 'mdi', 'mdj', 'mdk', 'mdl', 'mdm', 'mdn', 'mdp', 'mdq', 'mdr', 'mds', 'mdt', 'mdu', 'mdv', 'mdw', 'mdx', 'mdy', 'mdz', 'mea', 'meb', 'mec', 'med', 'mee', 'mef', 'meg', 'meh', 'mei', 'mej', 'mek', 'mel', 'mem', 'men', 'meo', 'mep', 'meq', 'mer', 'mes', 'met', 'meu', 'mev', 'mew', 'mey', 'mez', 'mfa', 'mfb', 'mfc', 'mfd', 'mfe', 'mff', 'mfg', 'mfh', 'mfi', 'mfj', 'mfk', 'mfl', 'mfm', 'mfn', 'mfo', 'mfp', 'mfq', 'mfr', 'mfs', 'mft', 'mfu', 'mfv', 'mfw', 'mfx', 'mfy', 'mfz', 'mga', 'mgb', 'mgc', 'mgd', 'mge', 'mgf', 'mgg', 'mgh', 'mgi', 'mgj', 'mgk', 'mgl', 'mgm', 'mgn', 'mgo', 'mgp', 'mgq', 'mgr', 'mgs', 'mgt', 'mgu', 'mgv', 'mgw', 'mgx', 'mgy', 'mgz', 'mha', 'mhb', 'mhc', 'mhd', 'mhe', 'mhf', 'mhg', 'mhh', 'mhi', 'mhj', 'mhk', 'mhl', 'mhm', 'mhn', 'mho', 'mhp', 'mhq', 'mhr', 'mhs', 'mht', 'mhu', 'mhw', 'mhx', 'mhy', 'mhz', 'mia', 'mib', 'mic', 'mid', 'mie', 'mif', 'mig', 'mih', 'mii', 'mij', 'mik', 'mil', 'mim', 'min', 'mio', 'mip', 'miq', 'mir', 'mis', 'mit', 'miu', 'miw', 'mix', 'miy', 'miz', 'mja', 'mjb', 'mjc', 'mjd', 'mje', 'mjg', 'mjh', 'mji', 'mjj', 'mjk', 'mjl', 'mjm', 'mjn', 'mjo', 'mjp', 'mjq', 'mjr', 'mjs', 'mjt', 'mju', 'mjv', 'mjw', 'mjx', 'mjy', 'mjz', 'mka', 'mkb', 'mkc', 'mke', 'mkf', 'mkg', 'mkh', 'mki', 'mkj', 'mkk', 'mkl', 'mkm', 'mkn', 'mko', 'mkp', 'mkq', 'mkr', 'mks', 'mkt', 'mku', 'mkv', 'mkw', 'mkx', 'mky', 'mkz', 'mla', 'mlb', 'mlc', 'mld', 'mle', 'mlf', 'mlh', 'mli', 'mlj', 'mlk', 'mll', 'mlm', 'mln', 'mlo', 'mlp', 'mlq', 'mlr', 'mls', 'mlu', 'mlv', 'mlw', 'mlx', 'mlz', 'mma', 'mmb', 'mmc', 'mmd', 'mme', 'mmf', 'mmg', 'mmh', 'mmi', 'mmj', 'mmk', 'mml', 'mmm', 'mmn', 'mmo', 'mmp', 'mmq', 'mmr', 'mmt', 'mmu', 'mmv', 'mmw', 'mmx', 'mmy', 'mmz', 'mna', 'mnb', 'mnc', 'mnd', 'mne', 'mnf', 'mng', 'mnh', 'mni', 'mnj', 'mnk', 'mnl', 'mnm', 'mnn', 'mno', 'mnp', 'mnq', 'mnr', 'mns', 'mnt', 'mnu', 'mnv', 'mnw', 'mnx', 'mny', 'mnz', 'moa', 'moc', 'mod', 'moe', 'mof', 'mog', 'moh', 'moi', 'moj', 'mok', 'mom', 'moo', 'mop', 'moq', 'mor', 'mos', 'mot', 'mou', 'mov', 'mow', 'mox', 'moy', 'moz', 'mpa', 'mpb', 'mpc', 'mpd', 'mpe', 'mpg', 'mph', 'mpi', 'mpj', 'mpk', 'mpl', 'mpm', 'mpn', 'mpo', 'mpp', 'mpq', 'mpr', 'mps', 'mpt', 'mpu', 'mpv', 'mpw', 'mpx', 'mpy', 'mpz', 'mqa', 'mqb', 'mqc', 'mqe', 'mqf', 'mqg', 'mqh', 'mqi', 'mqj', 'mqk', 'mql', 'mqm', 'mqn', 'mqo', 'mqp', 'mqq', 'mqr', 'mqs', 'mqt', 'mqu', 'mqv', 'mqw', 'mqx', 'mqy', 'mqz', 'mra', 'mrb', 'mrc', 'mrd', 'mre', 'mrf', 'mrg', 'mrh', 'mrj', 'mrk', 'mrl', 'mrm', 'mrn', 'mro', 'mrp', 'mrq', 'mrr', 'mrs', 'mrt', 'mru', 'mrv', 'mrw', 'mrx', 'mry', 'mrz', 'msb', 'msc', 'msd', 'mse', 'msf', 'msg', 'msh', 'msi', 'msj', 'msk', 'msl', 'msm', 'msn', 'mso', 'msp', 'msq', 'msr', 'mss', 'mst', 'msu', 'msv', 'msw', 'msx', 'msy', 'msz', 'mta', 'mtb', 'mtc', 'mtd', 'mte', 'mtf', 'mtg', 'mth', 'mti', 'mtj', 'mtk', 'mtl', 'mtm', 'mtn', 'mto', 'mtp', 'mtq', 'mtr', 'mts', 'mtt', 'mtu', 'mtv', 'mtw', 'mtx', 'mty', 'mua', 'mub', 'muc', 'mud', 'mue', 'mug', 'muh', 'mui', 'muj', 'muk', 'mul', 'mum', 'mun', 'muo', 'mup', 'muq', 'mur', 'mus', 'mut', 'muu', 'muv', 'mux', 'muy', 'muz', 'mva', 'mvb', 'mvd', 'mve', 'mvf', 'mvg', 'mvh', 'mvi', 'mvk', 'mvl', 'mvm', 'mvn', 'mvo', 'mvp', 'mvq', 'mvr', 'mvs', 'mvt', 'mvu', 'mvv', 'mvw', 'mvx', 'mvy', 'mvz', 'mwa', 'mwb', 'mwc', 'mwd', 'mwe', 'mwf', 'mwg', 'mwh', 'mwi', 'mwj', 'mwk', 'mwl', 'mwm', 'mwn', 'mwo', 'mwp', 'mwq', 'mwr', 'mws', 'mwt', 'mwu', 'mwv', 'mww', 'mwx', 'mwy', 'mwz', 'mxa', 'mxb', 'mxc', 'mxd', 'mxe', 'mxf', 'mxg', 'mxh', 'mxi', 'mxj', 'mxk', 'mxl', 'mxm', 'mxn', 'mxo', 'mxp', 'mxq', 'mxr', 'mxs', 'mxt', 'mxu', 'mxv', 'mxw', 'mxx', 'mxy', 'mxz', 'myb', 'myc', 'myd', 'mye', 'myf', 'myg', 'myh', 'myi', 'myj', 'myk', 'myl', 'mym', 'myn', 'myo', 'myp', 'myq', 'myr', 'mys', 'myt', 'myu', 'myv', 'myw', 'myx', 'myy', 'myz', 'mza', 'mzb', 'mzc', 'mzd', 'mze', 'mzg', 'mzh', 'mzi', 'mzj', 'mzk', 'mzl', 'mzm', 'mzn', 'mzo', 'mzp', 'mzq', 'mzr', 'mzs', 'mzt', 'mzu', 'mzv', 'mzw', 'mzx', 'mzy', 'mzz', 'naa', 'nab', 'nac', 'nad', 'nae', 'naf', 'nag', 'nah', 'nai', 'naj', 'nak', 'nal', 'nam', 'nan', 'nao', 'nap', 'naq', 'nar', 'nas', 'nat', 'naw', 'nax', 'nay', 'naz', 'nba', 'nbb', 'nbc', 'nbd', 'nbe', 'nbf', 'nbg', 'nbh', 'nbi', 'nbj', 'nbk', 'nbm', 'nbn', 'nbo', 'nbp', 'nbq', 'nbr', 'nbs', 'nbt', 'nbu', 'nbv', 'nbw', 'nbx', 'nby', 'nca', 'ncb', 'ncc', 'ncd', 'nce', 'ncf', 'ncg', 'nch', 'nci', 'ncj', 'nck', 'ncl', 'ncm', 'ncn', 'nco', 'ncp', 'ncq', 'ncr', 'ncs', 'nct', 'ncu', 'ncx', 'ncz', 'nda', 'ndb', 'ndc', 'ndd', 'ndf', 'ndg', 'ndh', 'ndi', 'ndj', 'ndk', 'ndl', 'ndm', 'ndn', 'ndp', 'ndq', 'ndr', 'nds', 'ndt', 'ndu', 'ndv', 'ndw', 'ndx', 'ndy', 'ndz', 'nea', 'neb', 'nec', 'ned', 'nee', 'nef', 'neg', 'neh', 'nei', 'nej', 'nek', 'nem', 'nen', 'neo', 'neq', 'ner', 'nes', 'net', 'neu', 'nev', 'new', 'nex', 'ney', 'nez', 'nfa', 'nfd', 'nfl', 'nfr', 'nfu', 'nga', 'ngb', 'ngc', 'ngd', 'nge', 'ngf', 'ngg', 'ngh', 'ngi', 'ngj', 'ngk', 'ngl', 'ngm', 'ngn', 'ngo', 'ngp', 'ngq', 'ngr', 'ngs', 'ngt', 'ngu', 'ngv', 'ngw', 'ngx', 'ngy', 'ngz', 'nha', 'nhb', 'nhc', 'nhd', 'nhe', 'nhf', 'nhg', 'nhh', 'nhi', 'nhk', 'nhm', 'nhn', 'nho', 'nhp', 'nhq', 'nhr', 'nht', 'nhu', 'nhv', 'nhw', 'nhx', 'nhy', 'nhz', 'nia', 'nib', 'nic', 'nid', 'nie', 'nif', 'nig', 'nih', 'nii', 'nij', 'nik', 'nil', 'nim', 'nin', 'nio', 'niq', 'nir', 'nis', 'nit', 'niu', 'niv', 'niw', 'nix', 'niy', 'niz', 'nja', 'njb', 'njd', 'njh', 'nji', 'njj', 'njl', 'njm', 'njn', 'njo', 'njr', 'njs', 'njt', 'nju', 'njx', 'njy', 'njz', 'nka', 'nkb', 'nkc', 'nkd', 'nke', 'nkf', 'nkg', 'nkh', 'nki', 'nkj', 'nkk', 'nkm', 'nkn', 'nko', 'nkp', 'nkq', 'nkr', 'nks', 'nkt', 'nku', 'nkv', 'nkw', 'nkx', 'nkz', 'nla', 'nlc', 'nle', 'nlg', 'nli', 'nlj', 'nlk', 'nll', 'nlm', 'nln', 'nlo', 'nlq', 'nlr', 'nlu', 'nlv', 'nlw', 'nlx', 'nly', 'nlz', 'nma', 'nmb', 'nmc', 'nmd', 'nme', 'nmf', 'nmg', 'nmh', 'nmi', 'nmj', 'nmk', 'nml', 'nmm', 'nmn', 'nmo', 'nmp', 'nmq', 'nmr', 'nms', 'nmt', 'nmu', 'nmv', 'nmw', 'nmx', 'nmy', 'nmz', 'nna', 'nnb', 'nnc', 'nnd', 'nne', 'nnf', 'nng', 'nnh', 'nni', 'nnj', 'nnk', 'nnl', 'nnm', 'nnn', 'nnp', 'nnq', 'nnr', 'nns', 'nnt', 'nnu', 'nnv', 'nnw', 'nnx', 'nny', 'nnz', 'noa', 'noc', 'nod', 'noe', 'nof', 'nog', 'noh', 'noi', 'noj', 'nok', 'nol', 'nom', 'non', 'noo', 'nop', 'noq', 'nos', 'not', 'nou', 'nov', 'now', 'noy', 'noz', 'npa', 'npb', 'npg', 'nph', 'npi', 'npl', 'npn', 'npo', 'nps', 'npu', 'npx', 'npy', 'nqg', 'nqk', 'nql', 'nqm', 'nqn', 'nqo', 'nqq', 'nqy', 'nra', 'nrb', 'nrc', 'nre', 'nrf', 'nrg', 'nri', 'nrk', 'nrl', 'nrm', 'nrn', 'nrp', 'nrr', 'nrt', 'nru', 'nrx', 'nrz', 'nsa', 'nsc', 'nsd', 'nse', 'nsf', 'nsg', 'nsh', 'nsi', 'nsk', 'nsl', 'nsm', 'nsn', 'nso', 'nsp', 'nsq', 'nsr', 'nss', 'nst', 'nsu', 'nsv', 'nsw', 'nsx', 'nsy', 'nsz', 'ntd', 'nte', 'ntg', 'nti', 'ntj', 'ntk', 'ntm', 'nto', 'ntp', 'ntr', 'nts', 'ntu', 'ntw', 'ntx', 'nty', 'ntz', 'nua', 'nub', 'nuc', 'nud', 'nue', 'nuf', 'nug', 'nuh', 'nui', 'nuj', 'nuk', 'nul', 'num', 'nun', 'nuo', 'nup', 'nuq', 'nur', 'nus', 'nut', 'nuu', 'nuv', 'nuw', 'nux', 'nuy', 'nuz', 'nvh', 'nvm', 'nvo', 'nwa', 'nwb', 'nwc', 'nwe', 'nwg', 'nwi', 'nwm', 'nwo', 'nwr', 'nwx', 'nwy', 'nxa', 'nxd', 'nxe', 'nxg', 'nxi', 'nxk', 'nxl', 'nxm', 'nxn', 'nxo', 'nxq', 'nxr', 'nxu', 'nxx', 'nyb', 'nyc', 'nyd', 'nye', 'nyf', 'nyg', 'nyh', 'nyi', 'nyj', 'nyk', 'nyl', 'nym', 'nyn', 'nyo', 'nyp', 'nyq', 'nyr', 'nys', 'nyt', 'nyu', 'nyv', 'nyw', 'nyx', 'nyy', 'nza', 'nzb', 'nzd', 'nzi', 'nzk', 'nzm', 'nzs', 'nzu', 'nzy', 'nzz', 'oaa', 'oac', 'oar', 'oav', 'obi', 'obk', 'obl', 'obm', 'obo', 'obr', 'obt', 'obu', 'oca', 'och', 'oco', 'ocu', 'oda', 'odk', 'odt', 'odu', 'ofo', 'ofs', 'ofu', 'ogb', 'ogc', 'oge', 'ogg', 'ogo', 'ogu', 'oht', 'ohu', 'oia', 'oin', 'ojb', 'ojc', 'ojg', 'ojp', 'ojs', 'ojv', 'ojw', 'oka', 'okb', 'okd', 'oke', 'okg', 'okh', 'oki', 'okj', 'okk', 'okl', 'okm', 'okn', 'oko', 'okr', 'oks', 'oku', 'okv', 'okx', 'ola', 'old', 'ole', 'olk', 'olm', 'olo', 'olr', 'olt', 'olu', 'oma', 'omb', 'omc', 'ome', 'omg', 'omi', 'omk', 'oml', 'omn', 'omo', 'omp', 'omq', 'omr', 'omt', 'omu', 'omv', 'omw', 'omx', 'ona', 'onb', 'one', 'ong', 'oni', 'onj', 'onk', 'onn', 'ono', 'onp', 'onr', 'ons', 'ont', 'onu', 'onw', 'onx', 'ood', 'oog', 'oon', 'oor', 'oos', 'opa', 'opk', 'opm', 'opo', 'opt', 'opy', 'ora', 'orc', 'ore', 'org', 'orh', 'orn', 'oro', 'orr', 'ors', 'ort', 'oru', 'orv', 'orw', 'orx', 'ory', 'orz', 'osa', 'osc', 'osi', 'oso', 'osp', 'ost', 'osu', 'osx', 'ota', 'otb', 'otd', 'ote', 'oti', 'otk', 'otl', 'otm', 'otn', 'oto', 'otq', 'otr', 'ots', 'ott', 'otu', 'otw', 'otx', 'oty', 'otz', 'oua', 'oub', 'oue', 'oui', 'oum', 'oun', 'ovd', 'owi', 'owl', 'oyb', 'oyd', 'oym', 'oyy', 'ozm', 'paa', 'pab', 'pac', 'pad', 'pae', 'paf', 'pag', 'pah', 'pai', 'pak', 'pal', 'pam', 'pao', 'pap', 'paq', 'par', 'pas', 'pat', 'pau', 'pav', 'paw', 'pax', 'pay', 'paz', 'pbb', 'pbc', 'pbe', 'pbf', 'pbg', 'pbh', 'pbi', 'pbl', 'pbm', 'pbn', 'pbo', 'pbp', 'pbr', 'pbs', 'pbt', 'pbu', 'pbv', 'pby', 'pbz', 'pca', 'pcb', 'pcc', 'pcd', 'pce', 'pcf', 'pcg', 'pch', 'pci', 'pcj', 'pck', 'pcl', 'pcm', 'pcn', 'pcp', 'pcr', 'pcw', 'pda', 'pdc', 'pdi', 'pdn', 'pdo', 'pdt', 'pdu', 'pea', 'peb', 'ped', 'pee', 'pef', 'peg', 'peh', 'pei', 'pej', 'pek', 'pel', 'pem', 'peo', 'pep', 'peq', 'pes', 'pev', 'pex', 'pey', 'pez', 'pfa', 'pfe', 'pfl', 'pga', 'pgd', 'pgg', 'pgi', 'pgk', 'pgl', 'pgn', 'pgs', 'pgu', 'pgy', 'pgz', 'pha', 'phd', 'phg', 'phh', 'phi', 'phk', 'phl', 'phm', 'phn', 'pho', 'phq', 'phr', 'pht', 'phu', 'phv', 'phw', 'pia', 'pib', 'pic', 'pid', 'pie', 'pif', 'pig', 'pih', 'pii', 'pij', 'pil', 'pim', 'pin', 'pio', 'pip', 'pir', 'pis', 'pit', 'piu', 'piv', 'piw', 'pix', 'piy', 'piz', 'pjt', 'pka', 'pkb', 'pkc', 'pkg', 'pkh', 'pkn', 'pko', 'pkp', 'pkr', 'pks', 'pkt', 'pku', 'pla', 'plb', 'plc', 'pld', 'ple', 'plf', 'plg', 'plh', 'plj', 'plk', 'pll', 'pln', 'plo', 'plp', 'plq', 'plr', 'pls', 'plt', 'plu', 'plv', 'plw', 'ply', 'plz', 'pma', 'pmb', 'pmc', 'pmd', 'pme', 'pmf', 'pmh', 'pmi', 'pmj', 'pmk', 'pml', 'pmm', 'pmn', 'pmo', 'pmq', 'pmr', 'pms', 'pmt', 'pmu', 'pmw', 'pmx', 'pmy', 'pmz', 'pna', 'pnb', 'pnc', 'pne', 'png', 'pnh', 'pni', 'pnj', 'pnk', 'pnl', 'pnm', 'pnn', 'pno', 'pnp', 'pnq', 'pnr', 'pns', 'pnt', 'pnu', 'pnv', 'pnw', 'pnx', 'pny', 'pnz', 'poc', 'pod', 'poe', 'pof', 'pog', 'poh', 'poi', 'pok', 'pom', 'pon', 'poo', 'pop', 'poq', 'pos', 'pot', 'pov', 'pow', 'pox', 'poy', 'poz', 'ppa', 'ppe', 'ppi', 'ppk', 'ppl', 'ppm', 'ppn', 'ppo', 'ppp', 'ppq', 'ppr', 'pps', 'ppt', 'ppu', 'pqa', 'pqe', 'pqm', 'pqw', 'pra', 'prb', 'prc', 'prd', 'pre', 'prf', 'prg', 'prh', 'pri', 'prk', 'prl', 'prm', 'prn', 'pro', 'prp', 'prq', 'prr', 'prs', 'prt', 'pru', 'prw', 'prx', 'pry', 'prz', 'psa', 'psc', 'psd', 'pse', 'psg', 'psh', 'psi', 'psl', 'psm', 'psn', 'pso', 'psp', 'psq', 'psr', 'pss', 'pst', 'psu', 'psw', 'psy', 'pta', 'pth', 'pti', 'ptn', 'pto', 'ptp', 'ptq', 'ptr', 'ptt', 'ptu', 'ptv', 'ptw', 'pty', 'pua', 'pub', 'puc', 'pud', 'pue', 'puf', 'pug', 'pui', 'puj', 'puk', 'pum', 'puo', 'pup', 'puq', 'pur', 'put', 'puu', 'puw', 'pux', 'puy', 'puz', 'pwa', 'pwb', 'pwg', 'pwi', 'pwm', 'pwn', 'pwo', 'pwr', 'pww', 'pxm', 'pye', 'pym', 'pyn', 'pys', 'pyu', 'pyx', 'pyy', 'pzn', 'qaa..qtz', 'qua', 'qub', 'quc', 'qud', 'quf', 'qug', 'quh', 'qui', 'quk', 'qul', 'qum', 'qun', 'qup', 'quq', 'qur', 'qus', 'quv', 'quw', 'qux', 'quy', 'quz', 'qva', 'qvc', 'qve', 'qvh', 'qvi', 'qvj', 'qvl', 'qvm', 'qvn', 'qvo', 'qvp', 'qvs', 'qvw', 'qvy', 'qvz', 'qwa', 'qwc', 'qwe', 'qwh', 'qwm', 'qws', 'qwt', 'qxa', 'qxc', 'qxh', 'qxl', 'qxn', 'qxo', 'qxp', 'qxq', 'qxr', 'qxs', 'qxt', 'qxu', 'qxw', 'qya', 'qyp', 'raa', 'rab', 'rac', 'rad', 'raf', 'rag', 'rah', 'rai', 'raj', 'rak', 'ral', 'ram', 'ran', 'rao', 'rap', 'raq', 'rar', 'ras', 'rat', 'rau', 'rav', 'raw', 'rax', 'ray', 'raz', 'rbb', 'rbk', 'rbl', 'rbp', 'rcf', 'rdb', 'rea', 'reb', 'ree', 'reg', 'rei', 'rej', 'rel', 'rem', 'ren', 'rer', 'res', 'ret', 'rey', 'rga', 'rge', 'rgk', 'rgn', 'rgr', 'rgs', 'rgu', 'rhg', 'rhp', 'ria', 'rie', 'rif', 'ril', 'rim', 'rin', 'rir', 'rit', 'riu', 'rjg', 'rji', 'rjs', 'rka', 'rkb', 'rkh', 'rki', 'rkm', 'rkt', 'rkw', 'rma', 'rmb', 'rmc', 'rmd', 'rme', 'rmf', 'rmg', 'rmh', 'rmi', 'rmk', 'rml', 'rmm', 'rmn', 'rmo', 'rmp', 'rmq', 'rmr', 'rms', 'rmt', 'rmu', 'rmv', 'rmw', 'rmx', 'rmy', 'rmz', 'rna', 'rnd', 'rng', 'rnl', 'rnn', 'rnp', 'rnr', 'rnw', 'roa', 'rob', 'roc', 'rod', 'roe', 'rof', 'rog', 'rol', 'rom', 'roo', 'rop', 'ror', 'rou', 'row', 'rpn', 'rpt', 'rri', 'rro', 'rrt', 'rsb', 'rsi', 'rsl', 'rsm', 'rtc', 'rth', 'rtm', 'rts', 'rtw', 'rub', 'ruc', 'rue', 'ruf', 'rug', 'ruh', 'rui', 'ruk', 'ruo', 'rup', 'ruq', 'rut', 'ruu', 'ruy', 'ruz', 'rwa', 'rwk', 'rwm', 'rwo', 'rwr', 'rxd', 'rxw', 'ryn', 'rys', 'ryu', 'rzh', 'saa', 'sab', 'sac', 'sad', 'sae', 'saf', 'sah', 'sai', 'saj', 'sak', 'sal', 'sam', 'sao', 'sap', 'saq', 'sar', 'sas', 'sat', 'sau', 'sav', 'saw', 'sax', 'say', 'saz', 'sba', 'sbb', 'sbc', 'sbd', 'sbe', 'sbf', 'sbg', 'sbh', 'sbi', 'sbj', 'sbk', 'sbl', 'sbm', 'sbn', 'sbo', 'sbp', 'sbq', 'sbr', 'sbs', 'sbt', 'sbu', 'sbv', 'sbw', 'sbx', 'sby', 'sbz', 'sca', 'scb', 'sce', 'scf', 'scg', 'sch', 'sci', 'sck', 'scl', 'scn', 'sco', 'scp', 'scq', 'scs', 'sct', 'scu', 'scv', 'scw', 'scx', 'sda', 'sdb', 'sdc', 'sde', 'sdf', 'sdg', 'sdh', 'sdj', 'sdk', 'sdl', 'sdm', 'sdn', 'sdo', 'sdp', 'sdr', 'sds', 'sdt', 'sdu', 'sdv', 'sdx', 'sdz', 'sea', 'seb', 'sec', 'sed', 'see', 'sef', 'seg', 'seh', 'sei', 'sej', 'sek', 'sel', 'sem', 'sen', 'seo', 'sep', 'seq', 'ser', 'ses', 'set', 'seu', 'sev', 'sew', 'sey', 'sez', 'sfb', 'sfe', 'sfm', 'sfs', 'sfw', 'sga', 'sgb', 'sgc', 'sgd', 'sge', 'sgg', 'sgh', 'sgi', 'sgj', 'sgk', 'sgl', 'sgm', 'sgn', 'sgo', 'sgp', 'sgr', 'sgs', 'sgt', 'sgu', 'sgw', 'sgx', 'sgy', 'sgz', 'sha', 'shb', 'shc', 'shd', 'she', 'shg', 'shh', 'shi', 'shj', 'shk', 'shl', 'shm', 'shn', 'sho', 'shp', 'shq', 'shr', 'shs', 'sht', 'shu', 'shv', 'shw', 'shx', 'shy', 'shz', 'sia', 'sib', 'sid', 'sie', 'sif', 'sig', 'sih', 'sii', 'sij', 'sik', 'sil', 'sim', 'sio', 'sip', 'siq', 'sir', 'sis', 'sit', 'siu', 'siv', 'siw', 'six', 'siy', 'siz', 'sja', 'sjb', 'sjd', 'sje', 'sjg', 'sjk', 'sjl', 'sjm', 'sjn', 'sjo', 'sjp', 'sjr', 'sjs', 'sjt', 'sju', 'sjw', 'ska', 'skb', 'skc', 'skd', 'ske', 'skf', 'skg', 'skh', 'ski', 'skj', 'skk', 'skm', 'skn', 'sko', 'skp', 'skq', 'skr', 'sks', 'skt', 'sku', 'skv', 'skw', 'skx', 'sky', 'skz', 'sla', 'slc', 'sld', 'sle', 'slf', 'slg', 'slh', 'sli', 'slj', 'sll', 'slm', 'sln', 'slp', 'slq', 'slr', 'sls', 'slt', 'slu', 'slw', 'slx', 'sly', 'slz', 'sma', 'smb', 'smc', 'smd', 'smf', 'smg', 'smh', 'smi', 'smj', 'smk', 'sml', 'smm', 'smn', 'smp', 'smq', 'smr', 'sms', 'smt', 'smu', 'smv', 'smw', 'smx', 'smy', 'smz', 'snb', 'snc', 'sne', 'snf', 'sng', 'snh', 'sni', 'snj', 'snk', 'snl', 'snm', 'snn', 'sno', 'snp', 'snq', 'snr', 'sns', 'snu', 'snv', 'snw', 'snx', 'sny', 'snz', 'soa', 'sob', 'soc', 'sod', 'soe', 'sog', 'soh', 'soi', 'soj', 'sok', 'sol', 'son', 'soo', 'sop', 'soq', 'sor', 'sos', 'sou', 'sov', 'sow', 'sox', 'soy', 'soz', 'spb', 'spc', 'spd', 'spe', 'spg', 'spi', 'spk', 'spl', 'spm', 'spn', 'spo', 'spp', 'spq', 'spr', 'sps', 'spt', 'spu', 'spv', 'spx', 'spy', 'sqa', 'sqh', 'sqj', 'sqk', 'sqm', 'sqn', 'sqo', 'sqq', 'sqr', 'sqs', 'sqt', 'squ', 'sra', 'srb', 'src', 'sre', 'srf', 'srg', 'srh', 'sri', 'srk', 'srl', 'srm', 'srn', 'sro', 'srq', 'srr', 'srs', 'srt', 'sru', 'srv', 'srw', 'srx', 'sry', 'srz', 'ssa', 'ssb', 'ssc', 'ssd', 'sse', 'ssf', 'ssg', 'ssh', 'ssi', 'ssj', 'ssk', 'ssl', 'ssm', 'ssn', 'sso', 'ssp', 'ssq', 'ssr', 'sss', 'sst', 'ssu', 'ssv', 'ssx', 'ssy', 'ssz', 'sta', 'stb', 'std', 'ste', 'stf', 'stg', 'sth', 'sti', 'stj', 'stk', 'stl', 'stm', 'stn', 'sto', 'stp', 'stq', 'str', 'sts', 'stt', 'stu', 'stv', 'stw', 'sty', 'sua', 'sub', 'suc', 'sue', 'sug', 'sui', 'suj', 'suk', 'sul', 'sum', 'suq', 'sur', 'sus', 'sut', 'suv', 'suw', 'sux', 'suy', 'suz', 'sva', 'svb', 'svc', 'sve', 'svk', 'svm', 'svr', 'svs', 'svx', 'swb', 'swc', 'swf', 'swg', 'swh', 'swi', 'swj', 'swk', 'swl', 'swm', 'swn', 'swo', 'swp', 'swq', 'swr', 'sws', 'swt', 'swu', 'swv', 'sww', 'swx', 'swy', 'sxb', 'sxc', 'sxe', 'sxg', 'sxk', 'sxl', 'sxm', 'sxn', 'sxo', 'sxr', 'sxs', 'sxu', 'sxw', 'sya', 'syb', 'syc', 'syd', 'syi', 'syk', 'syl', 'sym', 'syn', 'syo', 'syr', 'sys', 'syw', 'syx', 'syy', 'sza', 'szb', 'szc', 'szd', 'sze', 'szg', 'szl', 'szn', 'szp', 'szs', 'szv', 'szw', 'taa', 'tab', 'tac', 'tad', 'tae', 'taf', 'tag', 'tai', 'taj', 'tak', 'tal', 'tan', 'tao', 'tap', 'taq', 'tar', 'tas', 'tau', 'tav', 'taw', 'tax', 'tay', 'taz', 'tba', 'tbb', 'tbc', 'tbd', 'tbe', 'tbf', 'tbg', 'tbh', 'tbi', 'tbj', 'tbk', 'tbl', 'tbm', 'tbn', 'tbo', 'tbp', 'tbq', 'tbr', 'tbs', 'tbt', 'tbu', 'tbv', 'tbw', 'tbx', 'tby', 'tbz', 'tca', 'tcb', 'tcc', 'tcd', 'tce', 'tcf', 'tcg', 'tch', 'tci', 'tck', 'tcl', 'tcm', 'tcn', 'tco', 'tcp', 'tcq', 'tcs', 'tct', 'tcu', 'tcw', 'tcx', 'tcy', 'tcz', 'tda', 'tdb', 'tdc', 'tdd', 'tde', 'tdf', 'tdg', 'tdh', 'tdi', 'tdj', 'tdk', 'tdl', 'tdm', 'tdn', 'tdo', 'tdq', 'tdr', 'tds', 'tdt', 'tdu', 'tdv', 'tdx', 'tdy', 'tea', 'teb', 'tec', 'ted', 'tee', 'tef', 'teg', 'teh', 'tei', 'tek', 'tem', 'ten', 'teo', 'tep', 'teq', 'ter', 'tes', 'tet', 'teu', 'tev', 'tew', 'tex', 'tey', 'tez', 'tfi', 'tfn', 'tfo', 'tfr', 'tft', 'tga', 'tgb', 'tgc', 'tgd', 'tge', 'tgf', 'tgg', 'tgh', 'tgi', 'tgj', 'tgn', 'tgo', 'tgp', 'tgq', 'tgr', 'tgs', 'tgt', 'tgu', 'tgv', 'tgw', 'tgx', 'tgy', 'tgz', 'thc', 'thd', 'the', 'thf', 'thh', 'thi', 'thk', 'thl', 'thm', 'thn', 'thp', 'thq', 'thr', 'ths', 'tht', 'thu', 'thv', 'thw', 'thx', 'thy', 'thz', 'tia', 'tic', 'tid', 'tie', 'tif', 'tig', 'tih', 'tii', 'tij', 'tik', 'til', 'tim', 'tin', 'tio', 'tip', 'tiq', 'tis', 'tit', 'tiu', 'tiv', 'tiw', 'tix', 'tiy', 'tiz', 'tja', 'tjg', 'tji', 'tjl', 'tjm', 'tjn', 'tjo', 'tjs', 'tju', 'tjw', 'tka', 'tkb', 'tkd', 'tke', 'tkf', 'tkg', 'tkk', 'tkl', 'tkm', 'tkn', 'tkp', 'tkq', 'tkr', 'tks', 'tkt', 'tku', 'tkv', 'tkw', 'tkx', 'tkz', 'tla', 'tlb', 'tlc', 'tld', 'tlf', 'tlg', 'tlh', 'tli', 'tlj', 'tlk', 'tll', 'tlm', 'tln', 'tlo', 'tlp', 'tlq', 'tlr', 'tls', 'tlt', 'tlu', 'tlv', 'tlw', 'tlx', 'tly', 'tma', 'tmb', 'tmc', 'tmd', 'tme', 'tmf', 'tmg', 'tmh', 'tmi', 'tmj', 'tmk', 'tml', 'tmm', 'tmn', 'tmo', 'tmp', 'tmq', 'tmr', 'tms', 'tmt', 'tmu', 'tmv', 'tmw', 'tmy', 'tmz', 'tna', 'tnb', 'tnc', 'tnd', 'tne', 'tnf', 'tng', 'tnh', 'tni', 'tnk', 'tnl', 'tnm', 'tnn', 'tno', 'tnp', 'tnq', 'tnr', 'tns', 'tnt', 'tnu', 'tnv', 'tnw', 'tnx', 'tny', 'tnz', 'tob', 'toc', 'tod', 'toe', 'tof', 'tog', 'toh', 'toi', 'toj', 'tol', 'tom', 'too', 'top', 'toq', 'tor', 'tos', 'tou', 'tov', 'tow', 'tox', 'toy', 'toz', 'tpa', 'tpc', 'tpe', 'tpf', 'tpg', 'tpi', 'tpj', 'tpk', 'tpl', 'tpm', 'tpn', 'tpo', 'tpp', 'tpq', 'tpr', 'tpt', 'tpu', 'tpv', 'tpw', 'tpx', 'tpy', 'tpz', 'tqb', 'tql', 'tqm', 'tqn', 'tqo', 'tqp', 'tqq', 'tqr', 'tqt', 'tqu', 'tqw', 'tra', 'trb', 'trc', 'trd', 'tre', 'trf', 'trg', 'trh', 'tri', 'trj', 'trk', 'trl', 'trm', 'trn', 'tro', 'trp', 'trq', 'trr', 'trs', 'trt', 'tru', 'trv', 'trw', 'trx', 'try', 'trz', 'tsa', 'tsb', 'tsc', 'tsd', 'tse', 'tsf', 'tsg', 'tsh', 'tsi', 'tsj', 'tsk', 'tsl', 'tsm', 'tsp', 'tsq', 'tsr', 'tss', 'tst', 'tsu', 'tsv', 'tsw', 'tsx', 'tsy', 'tsz', 'tta', 'ttb', 'ttc', 'ttd', 'tte', 'ttf', 'ttg', 'tth', 'tti', 'ttj', 'ttk', 'ttl', 'ttm', 'ttn', 'tto', 'ttp', 'ttq', 'ttr', 'tts', 'ttt', 'ttu', 'ttv', 'ttw', 'tty', 'ttz', 'tua', 'tub', 'tuc', 'tud', 'tue', 'tuf', 'tug', 'tuh', 'tui', 'tuj', 'tul', 'tum', 'tun', 'tuo', 'tup', 'tuq', 'tus', 'tut', 'tuu', 'tuv', 'tuw', 'tux', 'tuy', 'tuz', 'tva', 'tvd', 'tve', 'tvk', 'tvl', 'tvm', 'tvn', 'tvo', 'tvs', 'tvt', 'tvu', 'tvw', 'tvy', 'twa', 'twb', 'twc', 'twd', 'twe', 'twf', 'twg', 'twh', 'twl', 'twm', 'twn', 'two', 'twp', 'twq', 'twr', 'twt', 'twu', 'tww', 'twx', 'twy', 'txa', 'txb', 'txc', 'txe', 'txg', 'txh', 'txi', 'txj', 'txm', 'txn', 'txo', 'txq', 'txr', 'txs', 'txt', 'txu', 'txx', 'txy', 'tya', 'tye', 'tyh', 'tyi', 'tyj', 'tyl', 'tyn', 'typ', 'tyr', 'tys', 'tyt', 'tyu', 'tyv', 'tyx', 'tyz', 'tza', 'tzh', 'tzj', 'tzl', 'tzm', 'tzn', 'tzo', 'tzx', 'uam', 'uan', 'uar', 'uba', 'ubi', 'ubl', 'ubr', 'ubu', 'uby', 'uda', 'ude', 'udg', 'udi', 'udj', 'udl', 'udm', 'udu', 'ues', 'ufi', 'uga', 'ugb', 'uge', 'ugn', 'ugo', 'ugy', 'uha', 'uhn', 'uis', 'uiv', 'uji', 'uka', 'ukg', 'ukh', 'ukk', 'ukl', 'ukp', 'ukq', 'uks', 'uku', 'ukw', 'uky', 'ula', 'ulb', 'ulc', 'ule', 'ulf', 'uli', 'ulk', 'ull', 'ulm', 'uln', 'ulu', 'ulw', 'uma', 'umb', 'umc', 'umd', 'umg', 'umi', 'umm', 'umn', 'umo', 'ump', 'umr', 'ums', 'umu', 'una', 'und', 'une', 'ung', 'unk', 'unm', 'unn', 'unp', 'unr', 'unu', 'unx', 'unz', 'uok', 'upi', 'upv', 'ura', 'urb', 'urc', 'ure', 'urf', 'urg', 'urh', 'uri', 'urj', 'urk', 'url', 'urm', 'urn', 'uro', 'urp', 'urr', 'urt', 'uru', 'urv', 'urw', 'urx', 'ury', 'urz', 'usa', 'ush', 'usi', 'usk', 'usp', 'usu', 'uta', 'ute', 'utp', 'utr', 'utu', 'uum', 'uun', 'uur', 'uuu', 'uve', 'uvh', 'uvl', 'uwa', 'uya', 'uzn', 'uzs', 'vaa', 'vae', 'vaf', 'vag', 'vah', 'vai', 'vaj', 'val', 'vam', 'van', 'vao', 'vap', 'var', 'vas', 'vau', 'vav', 'vay', 'vbb', 'vbk', 'vec', 'ved', 'vel', 'vem', 'veo', 'vep', 'ver', 'vgr', 'vgt', 'vic', 'vid', 'vif', 'vig', 'vil', 'vin', 'vis', 'vit', 'viv', 'vka', 'vki', 'vkj', 'vkk', 'vkl', 'vkm', 'vko', 'vkp', 'vkt', 'vku', 'vlp', 'vls', 'vma', 'vmb', 'vmc', 'vmd', 'vme', 'vmf', 'vmg', 'vmh', 'vmi', 'vmj', 'vmk', 'vml', 'vmm', 'vmp', 'vmq', 'vmr', 'vms', 'vmu', 'vmv', 'vmw', 'vmx', 'vmy', 'vmz', 'vnk', 'vnm', 'vnp', 'vor', 'vot', 'vra', 'vro', 'vrs', 'vrt', 'vsi', 'vsl', 'vsv', 'vto', 'vum', 'vun', 'vut', 'vwa', 'waa', 'wab', 'wac', 'wad', 'wae', 'waf', 'wag', 'wah', 'wai', 'waj', 'wak', 'wal', 'wam', 'wan', 'wao', 'wap', 'waq', 'war', 'was', 'wat', 'wau', 'wav', 'waw', 'wax', 'way', 'waz', 'wba', 'wbb', 'wbe', 'wbf', 'wbh', 'wbi', 'wbj', 'wbk', 'wbl', 'wbm', 'wbp', 'wbq', 'wbr', 'wbs', 'wbt', 'wbv', 'wbw', 'wca', 'wci', 'wdd', 'wdg', 'wdj', 'wdk', 'wdu', 'wdy', 'wea', 'wec', 'wed', 'weg', 'weh', 'wei', 'wem', 'wen', 'weo', 'wep', 'wer', 'wes', 'wet', 'weu', 'wew', 'wfg', 'wga', 'wgb', 'wgg', 'wgi', 'wgo', 'wgu', 'wgw', 'wgy', 'wha', 'whg', 'whk', 'whu', 'wib', 'wic', 'wie', 'wif', 'wig', 'wih', 'wii', 'wij', 'wik', 'wil', 'wim', 'win', 'wir', 'wit', 'wiu', 'wiv', 'wiw', 'wiy', 'wja', 'wji', 'wka', 'wkb', 'wkd', 'wkl', 'wku', 'wkw', 'wky', 'wla', 'wlc', 'wle', 'wlg', 'wli', 'wlk', 'wll', 'wlm', 'wlo', 'wlr', 'wls', 'wlu', 'wlv', 'wlw', 'wlx', 'wly', 'wma', 'wmb', 'wmc', 'wmd', 'wme', 'wmh', 'wmi', 'wmm', 'wmn', 'wmo', 'wms', 'wmt', 'wmw', 'wmx', 'wnb', 'wnc', 'wnd', 'wne', 'wng', 'wni', 'wnk', 'wnm', 'wnn', 'wno', 'wnp', 'wnu', 'wnw', 'wny', 'woa', 'wob', 'woc', 'wod', 'woe', 'wof', 'wog', 'woi', 'wok', 'wom', 'won', 'woo', 'wor', 'wos', 'wow', 'woy', 'wpc', 'wra', 'wrb', 'wrd', 'wrg', 'wrh', 'wri', 'wrk', 'wrl', 'wrm', 'wrn', 'wro', 'wrp', 'wrr', 'wrs', 'wru', 'wrv', 'wrw', 'wrx', 'wry', 'wrz', 'wsa', 'wsg', 'wsi', 'wsk', 'wsr', 'wss', 'wsu', 'wsv', 'wtf', 'wth', 'wti', 'wtk', 'wtm', 'wtw', 'wua', 'wub', 'wud', 'wuh', 'wul', 'wum', 'wun', 'wur', 'wut', 'wuu', 'wuv', 'wux', 'wuy', 'wwa', 'wwb', 'wwo', 'wwr', 'www', 'wxa', 'wxw', 'wya', 'wyb', 'wyi', 'wym', 'wyr', 'wyy', 'xaa', 'xab', 'xac', 'xad', 'xae', 'xag', 'xai', 'xaj', 'xak', 'xal', 'xam', 'xan', 'xao', 'xap', 'xaq', 'xar', 'xas', 'xat', 'xau', 'xav', 'xaw', 'xay', 'xba', 'xbb', 'xbc', 'xbd', 'xbe', 'xbg', 'xbi', 'xbj', 'xbm', 'xbn', 'xbo', 'xbp', 'xbr', 'xbw', 'xbx', 'xby', 'xcb', 'xcc', 'xce', 'xcg', 'xch', 'xcl', 'xcm', 'xcn', 'xco', 'xcr', 'xct', 'xcu', 'xcv', 'xcw', 'xcy', 'xda', 'xdc', 'xdk', 'xdm', 'xdo', 'xdy', 'xeb', 'xed', 'xeg', 'xel', 'xem', 'xep', 'xer', 'xes', 'xet', 'xeu', 'xfa', 'xga', 'xgb', 'xgd', 'xgf', 'xgg', 'xgi', 'xgl', 'xgm', 'xgn', 'xgr', 'xgu', 'xgw', 'xha', 'xhc', 'xhd', 'xhe', 'xhr', 'xht', 'xhu', 'xhv', 'xia', 'xib', 'xii', 'xil', 'xin', 'xip', 'xir', 'xis', 'xiv', 'xiy', 'xjb', 'xjt', 'xka', 'xkb', 'xkc', 'xkd', 'xke', 'xkf', 'xkg', 'xkh', 'xki', 'xkj', 'xkk', 'xkl', 'xkn', 'xko', 'xkp', 'xkq', 'xkr', 'xks', 'xkt', 'xku', 'xkv', 'xkw', 'xkx', 'xky', 'xkz', 'xla', 'xlb', 'xlc', 'xld', 'xle', 'xlg', 'xli', 'xln', 'xlo', 'xlp', 'xls', 'xlu', 'xly', 'xma', 'xmb', 'xmc', 'xmd', 'xme', 'xmf', 'xmg', 'xmh', 'xmj', 'xmk', 'xml', 'xmm', 'xmn', 'xmo', 'xmp', 'xmq', 'xmr', 'xms', 'xmt', 'xmu', 'xmv', 'xmw', 'xmx', 'xmy', 'xmz', 'xna', 'xnb', 'xnd', 'xng', 'xnh', 'xni', 'xnk', 'xnn', 'xno', 'xnr', 'xns', 'xnt', 'xnu', 'xny', 'xnz', 'xoc', 'xod', 'xog', 'xoi', 'xok', 'xom', 'xon', 'xoo', 'xop', 'xor', 'xow', 'xpa', 'xpc', 'xpe', 'xpg', 'xpi', 'xpj', 'xpk', 'xpm', 'xpn', 'xpo', 'xpp', 'xpq', 'xpr', 'xps', 'xpt', 'xpu', 'xpy', 'xqa', 'xqt', 'xra', 'xrb', 'xrd', 'xre', 'xrg', 'xri', 'xrm', 'xrn', 'xrq', 'xrr', 'xrt', 'xru', 'xrw', 'xsa', 'xsb', 'xsc', 'xsd', 'xse', 'xsh', 'xsi', 'xsj', 'xsl', 'xsm', 'xsn', 'xso', 'xsp', 'xsq', 'xsr', 'xss', 'xsu', 'xsv', 'xsy', 'xta', 'xtb', 'xtc', 'xtd', 'xte', 'xtg', 'xth', 'xti', 'xtj', 'xtl', 'xtm', 'xtn', 'xto', 'xtp', 'xtq', 'xtr', 'xts', 'xtt', 'xtu', 'xtv', 'xtw', 'xty', 'xtz', 'xua', 'xub', 'xud', 'xug', 'xuj', 'xul', 'xum', 'xun', 'xuo', 'xup', 'xur', 'xut', 'xuu', 'xve', 'xvi', 'xvn', 'xvo', 'xvs', 'xwa', 'xwc', 'xwd', 'xwe', 'xwg', 'xwj', 'xwk', 'xwl', 'xwo', 'xwr', 'xwt', 'xww', 'xxb', 'xxk', 'xxm', 'xxr', 'xxt', 'xya', 'xyb', 'xyj', 'xyk', 'xyl', 'xyt', 'xyy', 'xzh', 'xzm', 'xzp', 'yaa', 'yab', 'yac', 'yad', 'yae', 'yaf', 'yag', 'yah', 'yai', 'yaj', 'yak', 'yal', 'yam', 'yan', 'yao', 'yap', 'yaq', 'yar', 'yas', 'yat', 'yau', 'yav', 'yaw', 'yax', 'yay', 'yaz', 'yba', 'ybb', 'ybd', 'ybe', 'ybh', 'ybi', 'ybj', 'ybk', 'ybl', 'ybm', 'ybn', 'ybo', 'ybx', 'yby', 'ych', 'ycl', 'ycn', 'ycp', 'yda', 'ydd', 'yde', 'ydg', 'ydk', 'yds', 'yea', 'yec', 'yee', 'yei', 'yej', 'yel', 'yen', 'yer', 'yes', 'yet', 'yeu', 'yev', 'yey', 'yga', 'ygi', 'ygl', 'ygm', 'ygp', 'ygr', 'ygs', 'ygu', 'ygw', 'yha', 'yhd', 'yhl', 'yhs', 'yia', 'yif', 'yig', 'yih', 'yii', 'yij', 'yik', 'yil', 'yim', 'yin', 'yip', 'yiq', 'yir', 'yis', 'yit', 'yiu', 'yiv', 'yix', 'yiy', 'yiz', 'yka', 'ykg', 'yki', 'ykk', 'ykl', 'ykm', 'ykn', 'yko', 'ykr', 'ykt', 'yku', 'yky', 'yla', 'ylb', 'yle', 'ylg', 'yli', 'yll', 'ylm', 'yln', 'ylo', 'ylr', 'ylu', 'yly', 'yma', 'ymb', 'ymc', 'ymd', 'yme', 'ymg', 'ymh', 'ymi', 'ymk', 'yml', 'ymm', 'ymn', 'ymo', 'ymp', 'ymq', 'ymr', 'yms', 'ymt', 'ymx', 'ymz', 'yna', 'ynd', 'yne', 'yng', 'ynh', 'ynk', 'ynl', 'ynn', 'yno', 'ynq', 'yns', 'ynu', 'yob', 'yog', 'yoi', 'yok', 'yol', 'yom', 'yon', 'yos', 'yot', 'yox', 'yoy', 'ypa', 'ypb', 'ypg', 'yph', 'ypk', 'ypm', 'ypn', 'ypo', 'ypp', 'ypz', 'yra', 'yrb', 'yre', 'yri', 'yrk', 'yrl', 'yrm', 'yrn', 'yro', 'yrs', 'yrw', 'yry', 'ysc', 'ysd', 'ysg', 'ysl', 'ysn', 'yso', 'ysp', 'ysr', 'yss', 'ysy', 'yta', 'ytl', 'ytp', 'ytw', 'yty', 'yua', 'yub', 'yuc', 'yud', 'yue', 'yuf', 'yug', 'yui', 'yuj', 'yuk', 'yul', 'yum', 'yun', 'yup', 'yuq', 'yur', 'yut', 'yuu', 'yuw', 'yux', 'yuy', 'yuz', 'yva', 'yvt', 'ywa', 'ywg', 'ywl', 'ywn', 'ywq', 'ywr', 'ywt', 'ywu', 'yww', 'yxa', 'yxg', 'yxl', 'yxm', 'yxu', 'yxy', 'yyr', 'yyu', 'yyz', 'yzg', 'yzk', 'zaa', 'zab', 'zac', 'zad', 'zae', 'zaf', 'zag', 'zah', 'zai', 'zaj', 'zak', 'zal', 'zam', 'zao', 'zap', 'zaq', 'zar', 'zas', 'zat', 'zau', 'zav', 'zaw', 'zax', 'zay', 'zaz', 'zbc', 'zbe', 'zbl', 'zbt', 'zbw', 'zca', 'zch', 'zdj', 'zea', 'zeg', 'zeh', 'zen', 'zga', 'zgb', 'zgh', 'zgm', 'zgn', 'zgr', 'zhb', 'zhd', 'zhi', 'zhn', 'zhw', 'zhx', 'zia', 'zib', 'zik', 'zil', 'zim', 'zin', 'zir', 'ziw', 'ziz', 'zka', 'zkb', 'zkd', 'zkg', 'zkh', 'zkk', 'zkn', 'zko', 'zkp', 'zkr', 'zkt', 'zku', 'zkv', 'zkz', 'zle', 'zlj', 'zlm', 'zln', 'zlq', 'zls', 'zlw', 'zma', 'zmb', 'zmc', 'zmd', 'zme', 'zmf', 'zmg', 'zmh', 'zmi', 'zmj', 'zmk', 'zml', 'zmm', 'zmn', 'zmo', 'zmp', 'zmq', 'zmr', 'zms', 'zmt', 'zmu', 'zmv', 'zmw', 'zmx', 'zmy', 'zmz', 'zna', 'znd', 'zne', 'zng', 'znk', 'zns', 'zoc', 'zoh', 'zom', 'zoo', 'zoq', 'zor', 'zos', 'zpa', 'zpb', 'zpc', 'zpd', 'zpe', 'zpf', 'zpg', 'zph', 'zpi', 'zpj', 'zpk', 'zpl', 'zpm', 'zpn', 'zpo', 'zpp', 'zpq', 'zpr', 'zps', 'zpt', 'zpu', 'zpv', 'zpw', 'zpx', 'zpy', 'zpz', 'zqe', 'zra', 'zrg', 'zrn', 'zro', 'zrp', 'zrs', 'zsa', 'zsk', 'zsl', 'zsm', 'zsr', 'zsu', 'zte', 'ztg', 'ztl', 'ztm', 'ztn', 'ztp', 'ztq', 'zts', 'ztt', 'ztu', 'ztx', 'zty', 'zua', 'zuh', 'zum', 'zun', 'zuy', 'zwa', 'zxx', 'zyb', 'zyg', 'zyj', 'zyn', 'zyp', 'zza', 'zzj' ];
  axe.utils.validLangs = function() {
    'use strict';
    return langs;
  };
  'use strict';
  function _extends() {
    _extends = Object.assign || function(target) {
      for (var i = 1; i < arguments.length; i++) {
        var source = arguments[i];
        for (var key in source) {
          if (Object.prototype.hasOwnProperty.call(source, key)) {
            target[key] = source[key];
          }
        }
      }
      return target;
    };
    return _extends.apply(this, arguments);
  }
  function _toConsumableArray(arr) {
    return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _nonIterableSpread();
  }
  function _nonIterableSpread() {
    throw new TypeError('Invalid attempt to spread non-iterable instance');
  }
  function _iterableToArray(iter) {
    if (Symbol.iterator in Object(iter) || Object.prototype.toString.call(iter) === '[object Arguments]') {
      return Array.from(iter);
    }
  }
  function _arrayWithoutHoles(arr) {
    if (Array.isArray(arr)) {
      for (var i = 0, arr2 = new Array(arr.length); i < arr.length; i++) {
        arr2[i] = arr[i];
      }
      return arr2;
    }
  }
  function _slicedToArray(arr, i) {
    return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _nonIterableRest();
  }
  function _nonIterableRest() {
    throw new TypeError('Invalid attempt to destructure non-iterable instance');
  }
  function _iterableToArrayLimit(arr, i) {
    if (!(Symbol.iterator in Object(arr) || Object.prototype.toString.call(arr) === '[object Arguments]')) {
      return;
    }
    var _arr = [];
    var _n = true;
    var _d = false;
    var _e = undefined;
    try {
      for (var _i = arr[Symbol.iterator](), _s; !(_n = (_s = _i.next()).done); _n = true) {
        _arr.push(_s.value);
        if (i && _arr.length === i) {
          break;
        }
      }
    } catch (err) {
      _d = true;
      _e = err;
    } finally {
      try {
        if (!_n && _i['return'] != null) {
          _i['return']();
        }
      } finally {
        if (_d) {
          throw _e;
        }
      }
    }
    return _arr;
  }
  function _arrayWithHoles(arr) {
    if (Array.isArray(arr)) {
      return arr;
    }
  }
  function _typeof(obj) {
    '@babel/helpers - typeof';
    if (typeof Symbol === 'function' && typeof Symbol.iterator === 'symbol') {
      _typeof = function _typeof(obj) {
        return typeof obj;
      };
    } else {
      _typeof = function _typeof(obj) {
        return obj && typeof Symbol === 'function' && obj.constructor === Symbol && obj !== Symbol.prototype ? 'symbol' : typeof obj;
      };
    }
    return _typeof(obj);
  }
  axe._load({
    lang: 'en',
    data: {
      rules: {
        accesskeys: {
          description: 'Ensures every accesskey attribute value is unique',
          help: 'accesskey attribute value must be unique'
        },
        'area-alt': {
          description: 'Ensures <area> elements of image maps have alternate text',
          help: 'Active <area> elements must have alternate text'
        },
        'aria-allowed-attr': {
          description: 'Ensures ARIA attributes are allowed for an element\'s role',
          help: 'Elements must only use allowed ARIA attributes'
        },
        'aria-allowed-role': {
          description: 'Ensures role attribute has an appropriate value for the element',
          help: 'ARIA role must be appropriate for the element'
        },
        'aria-dpub-role-fallback': {
          description: 'Ensures unsupported DPUB roles are only used on elements with implicit fallback roles',
          help: 'Unsupported DPUB ARIA roles should be used on elements with implicit fallback roles'
        },
        'aria-hidden-body': {
          description: 'Ensures aria-hidden=\'true\' is not present on the document body.',
          help: 'aria-hidden=\'true\' must not be present on the document body'
        },
        'aria-hidden-focus': {
          description: 'Ensures aria-hidden elements do not contain focusable elements',
          help: 'ARIA hidden element must not contain focusable elements'
        },
        'aria-input-field-name': {
          description: 'Ensures every ARIA input field has an accessible name',
          help: 'ARIA input fields must have an accessible name'
        },
        'aria-required-attr': {
          description: 'Ensures elements with ARIA roles have all required ARIA attributes',
          help: 'Required ARIA attributes must be provided'
        },
        'aria-required-children': {
          description: 'Ensures elements with an ARIA role that require child roles contain them',
          help: 'Certain ARIA roles must contain particular children'
        },
        'aria-required-parent': {
          description: 'Ensures elements with an ARIA role that require parent roles are contained by them',
          help: 'Certain ARIA roles must be contained by particular parents'
        },
        'aria-roledescription': {
          description: 'Ensure aria-roledescription is only used on elements with an implicit or explicit role',
          help: 'Use aria-roledescription on elements with a semantic role'
        },
        'aria-roles': {
          description: 'Ensures all elements with a role attribute use a valid value',
          help: 'ARIA roles used must conform to valid values'
        },
        'aria-toggle-field-name': {
          description: 'Ensures every ARIA toggle field has an accessible name',
          help: 'ARIA toggle fields have an accessible name'
        },
        'aria-valid-attr-value': {
          description: 'Ensures all ARIA attributes have valid values',
          help: 'ARIA attributes must conform to valid values'
        },
        'aria-valid-attr': {
          description: 'Ensures attributes that begin with aria- are valid ARIA attributes',
          help: 'ARIA attributes must conform to valid names'
        },
        'audio-caption': {
          description: 'Ensures <audio> elements have captions',
          help: '<audio> elements must have a captions track'
        },
        'autocomplete-valid': {
          description: 'Ensure the autocomplete attribute is correct and suitable for the form field',
          help: 'autocomplete attribute must be used correctly'
        },
        'avoid-inline-spacing': {
          description: 'Ensure that text spacing set through style attributes can be adjusted with custom stylesheets',
          help: 'Inline text spacing must be adjustable with custom stylesheets'
        },
        blink: {
          description: 'Ensures <blink> elements are not used',
          help: '<blink> elements are deprecated and must not be used'
        },
        'button-name': {
          description: 'Ensures buttons have discernible text',
          help: 'Buttons must have discernible text'
        },
        bypass: {
          description: 'Ensures each page has at least one mechanism for a user to bypass navigation and jump straight to the content',
          help: 'Page must have means to bypass repeated blocks'
        },
        checkboxgroup: {
          description: 'Ensures related <input type="checkbox"> elements have a group and that the group designation is consistent',
          help: 'Checkbox inputs with the same name attribute value must be part of a group'
        },
        'color-contrast': {
          description: 'Ensures the contrast between foreground and background colors meets WCAG 2 AA contrast ratio thresholds',
          help: 'Elements must have sufficient color contrast'
        },
        'css-orientation-lock': {
          description: 'Ensures content is not locked to any specific display orientation, and the content is operable in all display orientations',
          help: 'CSS Media queries are not used to lock display orientation'
        },
        'definition-list': {
          description: 'Ensures <dl> elements are structured correctly',
          help: '<dl> elements must only directly contain properly-ordered <dt> and <dd> groups, <script>, <template> or <div> elements'
        },
        dlitem: {
          description: 'Ensures <dt> and <dd> elements are contained by a <dl>',
          help: '<dt> and <dd> elements must be contained by a <dl>'
        },
        'document-title': {
          description: 'Ensures each HTML document contains a non-empty <title> element',
          help: 'Documents must have <title> element to aid in navigation'
        },
        'duplicate-id-active': {
          description: 'Ensures every id attribute value of active elements is unique',
          help: 'IDs of active elements must be unique'
        },
        'duplicate-id-aria': {
          description: 'Ensures every id attribute value used in ARIA and in labels is unique',
          help: 'IDs used in ARIA and labels must be unique'
        },
        'duplicate-id': {
          description: 'Ensures every id attribute value is unique',
          help: 'id attribute value must be unique'
        },
        'empty-heading': {
          description: 'Ensures headings have discernible text',
          help: 'Headings must not be empty'
        },
        'focus-order-semantics': {
          description: 'Ensures elements in the focus order have an appropriate role',
          help: 'Elements in the focus order need a role appropriate for interactive content'
        },
        'form-field-multiple-labels': {
          description: 'Ensures form field does not have multiple label elements',
          help: 'Form field should not have multiple label elements'
        },
        'frame-tested': {
          description: 'Ensures <iframe> and <frame> elements contain the axe-core script',
          help: 'Frames must be tested with axe-core'
        },
        'frame-title-unique': {
          description: 'Ensures <iframe> and <frame> elements contain a unique title attribute',
          help: 'Frames must have a unique title attribute'
        },
        'frame-title': {
          description: 'Ensures <iframe> and <frame> elements contain a non-empty title attribute',
          help: 'Frames must have title attribute'
        },
        'heading-order': {
          description: 'Ensures the order of headings is semantically correct',
          help: 'Heading levels should only increase by one'
        },
        'hidden-content': {
          description: 'Informs users about hidden content.',
          help: 'Hidden content on the page cannot be analyzed'
        },
        'html-has-lang': {
          description: 'Ensures every HTML document has a lang attribute',
          help: '<html> element must have a lang attribute'
        },
        'html-lang-valid': {
          description: 'Ensures the lang attribute of the <html> element has a valid value',
          help: '<html> element must have a valid value for the lang attribute'
        },
        'html-xml-lang-mismatch': {
          description: 'Ensure that HTML elements with both valid lang and xml:lang attributes agree on the base language of the page',
          help: 'HTML elements with lang and xml:lang must have the same base language'
        },
        'identical-links-same-purpose': {
          description: 'Ensure that links with the same accessible name serve a similar purpose',
          help: 'Links with the same name have a similar purpose'
        },
        'image-alt': {
          description: 'Ensures <img> elements have alternate text or a role of none or presentation',
          help: 'Images must have alternate text'
        },
        'image-redundant-alt': {
          description: 'Ensure image alternative is not repeated as text',
          help: 'Alternative text of images should not be repeated as text'
        },
        'input-button-name': {
          description: 'Ensures input buttons have discernible text',
          help: 'Input buttons must have discernible text'
        },
        'input-image-alt': {
          description: 'Ensures <input type="image"> elements have alternate text',
          help: 'Image buttons must have alternate text'
        },
        'label-content-name-mismatch': {
          description: 'Ensures that elements labelled through their content must have their visible text as part of their accessible name',
          help: 'Elements must have their visible text as part of their accessible name'
        },
        'label-title-only': {
          description: 'Ensures that every form element is not solely labeled using the title or aria-describedby attributes',
          help: 'Form elements should have a visible label'
        },
        label: {
          description: 'Ensures every form element has a label',
          help: 'Form elements must have labels'
        },
        'landmark-banner-is-top-level': {
          description: 'Ensures the banner landmark is at top level',
          help: 'Banner landmark must not be contained in another landmark'
        },
        'landmark-complementary-is-top-level': {
          description: 'Ensures the complementary landmark or aside is at top level',
          help: 'Aside must not be contained in another landmark'
        },
        'landmark-contentinfo-is-top-level': {
          description: 'Ensures the contentinfo landmark is at top level',
          help: 'Contentinfo landmark must not be contained in another landmark'
        },
        'landmark-main-is-top-level': {
          description: 'Ensures the main landmark is at top level',
          help: 'Main landmark must not be contained in another landmark'
        },
        'landmark-no-duplicate-banner': {
          description: 'Ensures the document has at most one banner landmark',
          help: 'Document must not have more than one banner landmark'
        },
        'landmark-no-duplicate-contentinfo': {
          description: 'Ensures the document has at most one contentinfo landmark',
          help: 'Document must not have more than one contentinfo landmark'
        },
        'landmark-no-duplicate-main': {
          description: 'Ensures the document has at most one main landmark',
          help: 'Document must not have more than one main landmark'
        },
        'landmark-one-main': {
          description: 'Ensures the document has a main landmark',
          help: 'Document must have one main landmark'
        },
        'landmark-unique': {
          help: 'Ensures landmarks are unique',
          description: 'Landmarks must have a unique role or role/label/title (i.e. accessible name) combination'
        },
        'layout-table': {
          description: 'Ensures presentational <table> elements do not use <th>, <caption> elements or the summary attribute',
          help: 'Layout tables must not use data table elements'
        },
        'link-in-text-block': {
          description: 'Links can be distinguished without relying on color',
          help: 'Links must be distinguished from surrounding text in a way that does not rely on color'
        },
        'link-name': {
          description: 'Ensures links have discernible text',
          help: 'Links must have discernible text'
        },
        list: {
          description: 'Ensures that lists are structured correctly',
          help: '<ul> and <ol> must only directly contain <li>, <script> or <template> elements'
        },
        listitem: {
          description: 'Ensures <li> elements are used semantically',
          help: '<li> elements must be contained in a <ul> or <ol>'
        },
        marquee: {
          description: 'Ensures <marquee> elements are not used',
          help: '<marquee> elements are deprecated and must not be used'
        },
        'meta-refresh': {
          description: 'Ensures <meta http-equiv="refresh"> is not used',
          help: 'Timed refresh must not exist'
        },
        'meta-viewport-large': {
          description: 'Ensures <meta name="viewport"> can scale a significant amount',
          help: 'Users should be able to zoom and scale the text up to 500%'
        },
        'meta-viewport': {
          description: 'Ensures <meta name="viewport"> does not disable text scaling and zooming',
          help: 'Zooming and scaling must not be disabled'
        },
        'no-autoplay-audio': {
          description: 'Ensures <video> or <audio> elements do not autoplay audio for more than 3 seconds without a control mechanism to stop or mute the audio',
          help: '<video> or <audio> elements do not autoplay audio'
        },
        'object-alt': {
          description: 'Ensures <object> elements have alternate text',
          help: '<object> elements must have alternate text'
        },
        'p-as-heading': {
          description: 'Ensure p elements are not used to style headings',
          help: 'Bold, italic text and font-size are not used to style p elements as a heading'
        },
        'page-has-heading-one': {
          description: 'Ensure that the page, or at least one of its frames contains a level-one heading',
          help: 'Page must contain a level-one heading'
        },
        radiogroup: {
          description: 'Ensures related <input type="radio"> elements have a group and that the group designation is consistent',
          help: 'Radio inputs with the same name attribute value must be part of a group'
        },
        region: {
          description: 'Ensures all page content is contained by landmarks',
          help: 'All page content must be contained by landmarks'
        },
        'role-img-alt': {
          description: 'Ensures [role=\'img\'] elements have alternate text',
          help: '[role=\'img\'] elements have an alternative text'
        },
        'scope-attr-valid': {
          description: 'Ensures the scope attribute is used correctly on tables',
          help: 'scope attribute should be used correctly'
        },
        'scrollable-region-focusable': {
          description: 'Elements that have scrollable content should be accessible by keyboard',
          help: 'Ensure that scrollable region has keyboard access'
        },
        'server-side-image-map': {
          description: 'Ensures that server-side image maps are not used',
          help: 'Server-side image maps must not be used'
        },
        'skip-link': {
          description: 'Ensure all skip links have a focusable target',
          help: 'The skip-link target should exist and be focusable'
        },
        'svg-img-alt': {
          description: 'Ensures svg elements with an img, graphics-document or graphics-symbol role have an accessible text',
          help: 'svg elements with an img role have an alternative text'
        },
        tabindex: {
          description: 'Ensures tabindex attribute values are not greater than 0',
          help: 'Elements should not have tabindex greater than zero'
        },
        'table-duplicate-name': {
          description: 'Ensure that tables do not have the same summary and caption',
          help: 'The <caption> element should not contain the same text as the summary attribute'
        },
        'table-fake-caption': {
          description: 'Ensure that tables with a caption use the <caption> element.',
          help: 'Data or header cells should not be used to give caption to a data table.'
        },
        'td-has-header': {
          description: 'Ensure that each non-empty data cell in a large table has one or more table headers',
          help: 'All non-empty td element in table larger than 3 by 3 must have an associated table header'
        },
        'td-headers-attr': {
          description: 'Ensure that each cell in a table using the headers refers to another cell in that table',
          help: 'All cells in a table element that use the headers attribute must only refer to other cells of that same table'
        },
        'th-has-data-cells': {
          description: 'Ensure that each table header in a data table refers to data cells',
          help: 'All th elements and elements with role=columnheader/rowheader must have data cells they describe'
        },
        'valid-lang': {
          description: 'Ensures lang attributes have valid values',
          help: 'lang attribute must have a valid value'
        },
        'video-caption': {
          description: 'Ensures <video> elements have captions',
          help: '<video> elements must have captions'
        },
        'video-description': {
          description: 'Ensures <video> elements have audio descriptions',
          help: '<video> elements must have an audio description track'
        }
      },
      checks: {
        accesskeys: {
          impact: 'serious',
          messages: {
            pass: 'Accesskey attribute value is unique',
            fail: 'Document has multiple elements with the same accesskey'
          }
        },
        'non-empty-alt': {
          impact: 'critical',
          messages: {
            pass: 'Element has a non-empty alt attribute',
            fail: 'Element has no alt attribute or the alt attribute is empty'
          }
        },
        'non-empty-title': {
          impact: 'serious',
          messages: {
            pass: 'Element has a title attribute',
            fail: 'Element has no title attribute or the title attribute is empty'
          }
        },
        'aria-label': {
          impact: 'serious',
          messages: {
            pass: 'aria-label attribute exists and is not empty',
            fail: 'aria-label attribute does not exist or is empty'
          }
        },
        'aria-labelledby': {
          impact: 'serious',
          messages: {
            pass: 'aria-labelledby attribute exists and references elements that are visible to screen readers',
            fail: 'aria-labelledby attribute does not exist, references elements that do not exist or references elements that are empty'
          }
        },
        'aria-allowed-attr': {
          impact: 'critical',
          messages: {
            pass: 'ARIA attributes are used correctly for the defined role',
            fail: {
              singular: 'ARIA attribute is not allowed: ${data.values}',
              plural: 'ARIA attributes are not allowed: ${data.values}'
            }
          }
        },
        'aria-unsupported-attr': {
          impact: 'critical',
          messages: {
            pass: 'ARIA attribute is supported',
            fail: 'ARIA attribute is not widely supported in screen readers and assistive technologies: ${data.values}'
          }
        },
        'aria-allowed-role': {
          impact: 'minor',
          messages: {
            pass: 'ARIA role is allowed for given element',
            fail: {
              singular: 'ARIA role ${data.values} is not allowed for given element',
              plural: 'ARIA roles ${data.values} are not allowed for given element'
            },
            incomplete: {
              singular: 'ARIA role ${data.values} must be removed when the element is made visible, as it is not allowed for the element',
              plural: 'ARIA roles ${data.values} must be removed when the element is made visible, as they are not allowed for the element'
            }
          }
        },
        'implicit-role-fallback': {
          impact: 'moderate',
          messages: {
            pass: 'Element\u2019s implicit ARIA role is an appropriate fallback',
            fail: 'Element\u2019s implicit ARIA role is not a good fallback for the (unsupported) role'
          }
        },
        'aria-hidden-body': {
          impact: 'critical',
          messages: {
            pass: 'No aria-hidden attribute is present on document body',
            fail: 'aria-hidden=true should not be present on the document body'
          }
        },
        'focusable-modal-open': {
          impact: 'serious',
          messages: {
            pass: 'No focusable elements while a modal is open',
            incomplete: 'Check that focusable elements are not tabbable in the current state'
          }
        },
        'focusable-disabled': {
          impact: 'serious',
          messages: {
            pass: 'No focusable elements contained within element',
            fail: 'Focusable content should be disabled or be removed from the DOM'
          }
        },
        'focusable-not-tabbable': {
          impact: 'serious',
          messages: {
            pass: 'No focusable elements contained within element',
            fail: 'Focusable content should have tabindex=\'-1\' or be removed from the DOM'
          }
        },
        'no-implicit-explicit-label': {
          impact: 'moderate',
          messages: {
            pass: 'There is no mismatch between a <label> and accessible name',
            incomplete: 'Check that the <label> does not need be part of the ARIA ${data} field\'s name'
          }
        },
        'aria-required-attr': {
          impact: 'critical',
          messages: {
            pass: 'All required ARIA attributes are present',
            fail: {
              singular: 'Required ARIA attribute not present: ${data.values}',
              plural: 'Required ARIA attributes not present: ${data.values}'
            }
          }
        },
        'aria-required-children': {
          impact: 'critical',
          messages: {
            pass: 'Required ARIA children are present',
            fail: {
              singular: 'Required ARIA child role not present: ${data.values}',
              plural: 'Required ARIA children role not present: ${data.values}'
            },
            incomplete: {
              singular: 'Expecting ARIA child role to be added: ${data.values}',
              plural: 'Expecting ARIA children role to be added: ${data.values}'
            }
          }
        },
        'aria-required-parent': {
          impact: 'critical',
          messages: {
            pass: 'Required ARIA parent role present',
            fail: {
              singular: 'Required ARIA parent role not present: ${data.values}',
              plural: 'Required ARIA parents role not present: ${data.values}'
            }
          }
        },
        'aria-roledescription': {
          impact: 'serious',
          messages: {
            pass: 'aria-roledescription used on a supported semantic role',
            incomplete: 'Check that the aria-roledescription is announced by supported screen readers',
            fail: 'Give the element a role that supports aria-roledescription'
          }
        },
        fallbackrole: {
          impact: 'serious',
          messages: {
            pass: 'Only one role value used',
            fail: 'Use only one role value, since fallback roles are not supported in older browsers'
          }
        },
        invalidrole: {
          impact: 'critical',
          messages: {
            pass: 'ARIA role is valid',
            fail: {
              singular: 'Role must be one of the valid ARIA roles: ${data.values}',
              plural: 'Roles must be one of the valid ARIA roles: ${data.values}'
            }
          }
        },
        abstractrole: {
          impact: 'serious',
          messages: {
            pass: 'Abstract roles are not used',
            fail: {
              singular: 'Abstract role cannot be directly used: ${data.values}',
              plural: 'Abstract roles cannot be directly used: ${data.values}'
            }
          }
        },
        unsupportedrole: {
          impact: 'critical',
          messages: {
            pass: 'ARIA role is supported',
            fail: 'The role used is not widely supported in screen readers and assistive technologies: ${data.values}'
          }
        },
        'has-visible-text': {
          impact: 'minor',
          messages: {
            pass: 'Element has text that is visible to screen readers',
            fail: 'Element does not have text that is visible to screen readers'
          }
        },
        'aria-valid-attr-value': {
          impact: 'critical',
          messages: {
            pass: 'ARIA attribute values are valid',
            fail: {
              singular: 'Invalid ARIA attribute value: ${data.values}',
              plural: 'Invalid ARIA attribute values: ${data.values}'
            },
            incomplete: {
              noId: 'ARIA attribute element ID does not exist on the page: ${data.needsReview}',
              ariaCurrent: 'ARIA attribute value is invalid and will be treated as "aria-current=true": ${data.needsReview}'
            }
          }
        },
        'aria-errormessage': {
          impact: 'critical',
          messages: {
            pass: 'Uses a supported aria-errormessage technique',
            fail: {
              singular: 'aria-errormessage value `${data.values}` must use a technique to announce the message (e.g., aria-live, aria-describedby, role=alert, etc.)',
              plural: 'aria-errormessage values `${data.values}` must use a technique to announce the message (e.g., aria-live, aria-describedby, role=alert, etc.)'
            }
          }
        },
        'aria-valid-attr': {
          impact: 'critical',
          messages: {
            pass: 'ARIA attribute name is valid',
            fail: {
              singular: 'Invalid ARIA attribute name: ${data.values}',
              plural: 'Invalid ARIA attribute names: ${data.values}'
            }
          }
        },
        caption: {
          impact: 'critical',
          messages: {
            pass: 'The multimedia element has a captions track',
            incomplete: 'Check that captions is available for the element'
          }
        },
        'autocomplete-valid': {
          impact: 'serious',
          messages: {
            pass: 'the autocomplete attribute is correctly formatted',
            fail: 'the autocomplete attribute is incorrectly formatted'
          }
        },
        'autocomplete-appropriate': {
          impact: 'serious',
          messages: {
            pass: 'the autocomplete value is on an appropriate element',
            fail: 'the autocomplete value is inappropriate for this type of input'
          }
        },
        'avoid-inline-spacing': {
          impact: 'serious',
          messages: {
            pass: 'No inline styles with \'!important\' that affect text spacing has been specified',
            fail: {
              singular: 'Remove \'!important\' from inline style ${data.values}, as overriding this is not supported by most browsers',
              plural: 'Remove \'!important\' from inline styles ${data.values}, as overriding this is not supported by most browsers'
            }
          }
        },
        'is-on-screen': {
          impact: 'serious',
          messages: {
            pass: 'Element is not visible',
            fail: 'Element is visible'
          }
        },
        'button-has-visible-text': {
          impact: 'critical',
          messages: {
            pass: 'Element has inner text that is visible to screen readers',
            fail: 'Element does not have inner text that is visible to screen readers'
          }
        },
        'role-presentation': {
          impact: 'minor',
          messages: {
            pass: 'Element\'s default semantics were overriden with role="presentation"',
            fail: 'Element\'s default semantics were not overridden with role="presentation"'
          }
        },
        'role-none': {
          impact: 'minor',
          messages: {
            pass: 'Element\'s default semantics were overriden with role="none"',
            fail: 'Element\'s default semantics were not overridden with role="none"'
          }
        },
        'internal-link-present': {
          impact: 'serious',
          messages: {
            pass: 'Valid skip link found',
            fail: 'No valid skip link found'
          }
        },
        'header-present': {
          impact: 'serious',
          messages: {
            pass: 'Page has a heading',
            fail: 'Page does not have a heading'
          }
        },
        landmark: {
          impact: 'serious',
          messages: {
            pass: 'Page has a landmark region',
            fail: 'Page does not have a landmark region'
          }
        },
        'group-labelledby': {
          impact: 'critical',
          messages: {
            pass: 'Elements with the name "${data.name}" have both a shared label, and a unique label, referenced through aria-labelledby',
            fail: {
              default: 'Elements with the name "${data.name}" do not all have both a shared label, and a unique label referenced through aria-labelledby',
              'no-shared-label': 'Elements with the name "${data.name}" do not all have a shared label referenced through aria-labelledby',
              'no-unique-label': 'Elements with the name "${data.name}" do not all have a unique label referenced through aria-labelledby'
            }
          }
        },
        fieldset: {
          impact: 'critical',
          messages: {
            pass: 'Element is contained in a fieldset',
            fail: {
              default: 'Element does not have a containing fieldset or ARIA group',
              'no-legend': 'Fieldset does not have a legend as its first child',
              'empty-legend': 'Legend does not have text that is visible to screen readers',
              'mixed-inputs': 'Fieldset contains unrelated inputs',
              'no-group-label': 'ARIA group does not have aria-label or aria-labelledby',
              'group-mixed-inputs': 'ARIA group contains unrelated inputs'
            }
          }
        },
        'color-contrast': {
          impact: 'serious',
          messages: {
            pass: 'Element has sufficient color contrast of ${data.contrastRatio}',
            fail: 'Element has insufficient color contrast of ${data.contrastRatio} (foreground color: ${data.fgColor}, background color: ${data.bgColor}, font size: ${data.fontSize}, font weight: ${data.fontWeight}). Expected contrast ratio of ${data.expectedContrastRatio}',
            incomplete: {
              default: 'Unable to determine contrast ratio',
              bgImage: 'Element\'s background color could not be determined due to a background image',
              bgGradient: 'Element\'s background color could not be determined due to a background gradient',
              imgNode: 'Element\'s background color could not be determined because element contains an image node',
              bgOverlap: 'Element\'s background color could not be determined because it is overlapped by another element',
              fgAlpha: 'Element\'s foreground color could not be determined because of alpha transparency',
              elmPartiallyObscured: 'Element\'s background color could not be determined because it\'s partially obscured by another element',
              elmPartiallyObscuring: 'Element\'s background color could not be determined because it partially overlaps other elements',
              outsideViewport: 'Element\'s background color could not be determined because it\'s outside the viewport',
              equalRatio: 'Element has a 1:1 contrast ratio with the background',
              shortTextContent: 'Element content is too short to determine if it is actual text content',
              nonBmp: 'Element content contains only non-text characters'
            }
          }
        },
        'css-orientation-lock': {
          impact: 'serious',
          messages: {
            pass: 'Display is operable, and orientation lock does not exist',
            fail: 'CSS Orientation lock is applied, and makes display inoperable',
            incomplete: 'CSS Orientation lock cannot be determined'
          }
        },
        'structured-dlitems': {
          impact: 'serious',
          messages: {
            pass: 'When not empty, element has both <dt> and <dd> elements',
            fail: 'When not empty, element does not have at least one <dt> element followed by at least one <dd> element'
          }
        },
        'only-dlitems': {
          impact: 'serious',
          messages: {
            pass: 'List element only has direct children that are allowed inside <dt> or <dd> elements',
            fail: 'List element has direct children that are not allowed inside <dt> or <dd> elements'
          }
        },
        dlitem: {
          impact: 'serious',
          messages: {
            pass: 'Description list item has a <dl> parent element',
            fail: 'Description list item does not have a <dl> parent element'
          }
        },
        'doc-has-title': {
          impact: 'serious',
          messages: {
            pass: 'Document has a non-empty <title> element',
            fail: 'Document does not have a non-empty <title> element'
          }
        },
        'duplicate-id-active': {
          impact: 'serious',
          messages: {
            pass: 'Document has no active elements that share the same id attribute',
            fail: 'Document has active elements with the same id attribute: ${data}'
          }
        },
        'duplicate-id-aria': {
          impact: 'critical',
          messages: {
            pass: 'Document has no elements referenced with ARIA or labels that share the same id attribute',
            fail: 'Document has multiple elements referenced with ARIA with the same id attribute: ${data}'
          }
        },
        'duplicate-id': {
          impact: 'minor',
          messages: {
            pass: 'Document has no static elements that share the same id attribute',
            fail: 'Document has multiple static elements with the same id attribute'
          }
        },
        'has-widget-role': {
          impact: 'minor',
          messages: {
            pass: 'Element has a widget role.',
            fail: 'Element does not have a widget role.'
          }
        },
        'valid-scrollable-semantics': {
          impact: 'minor',
          messages: {
            pass: 'Element has valid semantics for an element in the focus order.',
            fail: 'Element has invalid semantics for an element in the focus order.'
          }
        },
        'multiple-label': {
          impact: 'moderate',
          messages: {
            pass: 'Form field does not have multiple label elements',
            incomplete: 'Multiple label elements is not widely supported in assistive technologies. Ensure the first label contains all necessary information.'
          }
        },
        'frame-tested': {
          impact: 'critical',
          messages: {
            pass: 'The iframe was tested with axe-core',
            fail: 'The iframe could not be tested with axe-core',
            incomplete: 'The iframe still has to be tested with axe-core'
          }
        },
        'unique-frame-title': {
          impact: 'serious',
          messages: {
            pass: 'Element\'s title attribute is unique',
            fail: 'Element\'s title attribute is not unique'
          }
        },
        'heading-order': {
          impact: 'moderate',
          messages: {
            pass: 'Heading order valid',
            fail: 'Heading order invalid'
          }
        },
        'hidden-content': {
          impact: 'minor',
          messages: {
            pass: 'All content on the page has been analyzed.',
            fail: 'There were problems analyzing the content on this page.',
            incomplete: 'There is hidden content on the page that was not analyzed. You will need to trigger the display of this content in order to analyze it.'
          }
        },
        'has-lang': {
          impact: 'serious',
          messages: {
            pass: 'The <html> element has a lang attribute',
            fail: {
              noXHTML: 'The xml:lang attribute is not valid on HTML pages, use the lang attribute.',
              noLang: 'The <html> element does not have a lang attribute'
            }
          }
        },
        'valid-lang': {
          impact: 'serious',
          messages: {
            pass: 'Value of lang attribute is included in the list of valid languages',
            fail: 'Value of lang attribute not included in the list of valid languages'
          }
        },
        'xml-lang-mismatch': {
          impact: 'moderate',
          messages: {
            pass: 'Lang and xml:lang attributes have the same base language',
            fail: 'Lang and xml:lang attributes do not have the same base language'
          }
        },
        'identical-links-same-purpose': {
          impact: 'minor',
          messages: {
            pass: 'There are no other links with the same name, that go to a different URL',
            incomplete: 'Check that links have the same purpose, or are intentionally ambiguous.'
          }
        },
        'has-alt': {
          impact: 'critical',
          messages: {
            pass: 'Element has an alt attribute',
            fail: 'Element does not have an alt attribute'
          }
        },
        'alt-space-value': {
          impact: 'critical',
          messages: {
            pass: 'Element has a valid alt attribute value',
            fail: 'Element has an alt attribute containing only a space character, which is not ignored by all screen readers'
          }
        },
        'duplicate-img-label': {
          impact: 'minor',
          messages: {
            pass: 'Element does not duplicate existing text in <img> alt text',
            fail: 'Element contains <img> element with alt text that duplicates existing text'
          }
        },
        'non-empty-if-present': {
          impact: 'critical',
          messages: {
            pass: {
              default: 'Element does not have a value attribute',
              'has-label': 'Element has a non-empty value attribute'
            },
            fail: 'Element has a value attribute and the value attribute is empty'
          }
        },
        'non-empty-value': {
          impact: 'critical',
          messages: {
            pass: 'Element has a non-empty value attribute',
            fail: 'Element has no value attribute or the value attribute is empty'
          }
        },
        'label-content-name-mismatch': {
          impact: 'serious',
          messages: {
            pass: 'Element contains visible text as part of it\'s accessible name',
            fail: 'Text inside the element is not included in the accessible name'
          }
        },
        'title-only': {
          impact: 'serious',
          messages: {
            pass: 'Form element does not solely use title attribute for its label',
            fail: 'Only title used to generate label for form element'
          }
        },
        'implicit-label': {
          impact: 'critical',
          messages: {
            pass: 'Form element has an implicit (wrapped) <label>',
            fail: 'Form element does not have an implicit (wrapped) <label>'
          }
        },
        'explicit-label': {
          impact: 'critical',
          messages: {
            pass: 'Form element has an explicit <label>',
            fail: 'Form element does not have an explicit <label>'
          }
        },
        'help-same-as-label': {
          impact: 'minor',
          messages: {
            pass: 'Help text (title or aria-describedby) does not duplicate label text',
            fail: 'Help text (title or aria-describedby) text is the same as the label text'
          }
        },
        'hidden-explicit-label': {
          impact: 'critical',
          messages: {
            pass: 'Form element has a visible explicit <label>',
            fail: 'Form element has explicit <label> that is hidden'
          }
        },
        'landmark-is-top-level': {
          impact: 'moderate',
          messages: {
            pass: 'The ${data.role} landmark is at the top level.',
            fail: 'The ${data.role} landmark is contained in another landmark.'
          }
        },
        'page-no-duplicate-banner': {
          impact: 'moderate',
          messages: {
            pass: 'Document does not have more than one banner landmark',
            fail: 'Document has more than one banner landmark'
          }
        },
        'page-no-duplicate-contentinfo': {
          impact: 'moderate',
          messages: {
            pass: 'Document does not have more than one contentinfo landmark',
            fail: 'Document has more than one contentinfo landmark'
          }
        },
        'page-no-duplicate-main': {
          impact: 'moderate',
          messages: {
            pass: 'Document does not have more than one main landmark',
            fail: 'Document has more than one main landmark'
          }
        },
        'page-has-main': {
          impact: 'moderate',
          messages: {
            pass: 'Document has at least one main landmark',
            fail: 'Document does not have a main landmark'
          }
        },
        'landmark-is-unique': {
          impact: 'moderate',
          messages: {
            pass: 'Landmarks must have a unique role or role/label/title (i.e. accessible name) combination',
            fail: 'The landmark must have a unique aria-label, aria-labelledby, or title to make landmarks distinguishable'
          }
        },
        'has-th': {
          impact: 'serious',
          messages: {
            pass: 'Layout table does not use <th> elements',
            fail: 'Layout table uses <th> elements'
          }
        },
        'has-caption': {
          impact: 'serious',
          messages: {
            pass: 'Layout table does not use <caption> element',
            fail: 'Layout table uses <caption> element'
          }
        },
        'has-summary': {
          impact: 'serious',
          messages: {
            pass: 'Layout table does not use summary attribute',
            fail: 'Layout table uses summary attribute'
          }
        },
        'link-in-text-block': {
          impact: 'serious',
          messages: {
            pass: 'Links can be distinguished from surrounding text in some way other than by color',
            fail: 'Links need to be distinguished from surrounding text in some way other than by color',
            incomplete: {
              default: 'Unable to determine contrast ratio',
              bgContrast: 'Element\'s contrast ratio could not be determined. Check for a distinct hover/focus style',
              bgImage: 'Element\'s contrast ratio could not be determined due to a background image',
              bgGradient: 'Element\'s contrast ratio could not be determined due to a background gradient',
              imgNode: 'Element\'s contrast ratio could not be determined because element contains an image node',
              bgOverlap: 'Element\'s contrast ratio could not be determined because of element overlap'
            }
          }
        },
        'focusable-no-name': {
          impact: 'serious',
          messages: {
            pass: 'Element is not in tab order or has accessible text',
            fail: 'Element is in tab order and does not have accessible text'
          }
        },
        'only-listitems': {
          impact: 'serious',
          messages: {
            pass: 'List element only has direct children that are allowed inside <li> elements',
            fail: {
              default: 'List element has direct children that are not allowed inside <li> elements',
              roleNotValid: 'List element has direct children with a role that is not allowed: ${data.roles}'
            }
          }
        },
        listitem: {
          impact: 'serious',
          messages: {
            pass: 'List item has a <ul>, <ol> or role="list" parent element',
            fail: {
              default: 'List item does not have a <ul>, <ol> parent element',
              roleNotValid: 'List item does not have a <ul>, <ol> parent element without a role, or a role="list"'
            }
          }
        },
        'meta-refresh': {
          impact: 'critical',
          messages: {
            pass: '<meta> tag does not immediately refresh the page',
            fail: '<meta> tag forces timed refresh of page'
          }
        },
        'meta-viewport-large': {
          impact: 'minor',
          messages: {
            pass: '<meta> tag does not prevent significant zooming on mobile devices',
            fail: '<meta> tag limits zooming on mobile devices'
          }
        },
        'meta-viewport': {
          impact: 'critical',
          messages: {
            pass: '<meta> tag does not disable zooming on mobile devices',
            fail: '${data} on <meta> tag disables zooming on mobile devices'
          }
        },
        'no-autoplay-audio': {
          impact: 'moderate',
          messages: {
            pass: '<video> or <audio> does not output audio for more than allowed duration or has controls mechanism',
            fail: '<video> or <audio> outputs audio for more than allowed duration and does not have a controls mechanism',
            incomplete: 'Check that the <video> or <audio> does not output audio for more than allowed duration or provides a controls mechanism'
          }
        },
        'p-as-heading': {
          impact: 'serious',
          messages: {
            pass: '<p> elements are not styled as headings',
            fail: 'Heading elements should be used instead of styled p elements'
          }
        },
        'page-has-heading-one': {
          impact: 'moderate',
          messages: {
            pass: 'Page has at least one level-one heading',
            fail: 'Page must have a level-one heading'
          }
        },
        region: {
          impact: 'moderate',
          messages: {
            pass: 'All page content is contained by landmarks',
            fail: 'Some page content is not contained by landmarks'
          }
        },
        'html5-scope': {
          impact: 'moderate',
          messages: {
            pass: 'Scope attribute is only used on table header elements (<th>)',
            fail: 'In HTML 5, scope attributes may only be used on table header elements (<th>)'
          }
        },
        'scope-value': {
          impact: 'critical',
          messages: {
            pass: 'Scope attribute is used correctly',
            fail: 'The value of the scope attribute may only be \'row\' or \'col\''
          }
        },
        'focusable-content': {
          impact: 'moderate',
          messages: {
            pass: 'Element contains focusable elements',
            fail: 'Element should have focusable content'
          }
        },
        'focusable-element': {
          impact: 'moderate',
          messages: {
            pass: 'Element is focusable',
            fail: 'Element should be focusable'
          }
        },
        exists: {
          impact: 'minor',
          messages: {
            pass: 'Element does not exist',
            incomplete: 'Element exists'
          }
        },
        'skip-link': {
          impact: 'moderate',
          messages: {
            pass: 'Skip link target exists',
            incomplete: 'Skip link target should become visible on activation',
            fail: 'No skip link target'
          }
        },
        'svg-non-empty-title': {
          impact: 'serious',
          messages: {
            pass: 'element has a child that is a title',
            fail: 'element has no child that is a title'
          }
        },
        tabindex: {
          impact: 'serious',
          messages: {
            pass: 'Element does not have a tabindex greater than 0',
            fail: 'Element has a tabindex greater than 0'
          }
        },
        'same-caption-summary': {
          impact: 'minor',
          messages: {
            pass: 'Content of summary attribute and <caption> are not duplicated',
            fail: 'Content of summary attribute and <caption> element are identical'
          }
        },
        'caption-faked': {
          impact: 'serious',
          messages: {
            pass: 'The first row of a table is not used as a caption',
            fail: 'The first child of the table should be a caption instead of a table cell'
          }
        },
        'td-has-header': {
          impact: 'critical',
          messages: {
            pass: 'All non-empty data cells have table headers',
            fail: 'Some non-empty data cells do not have table headers'
          }
        },
        'td-headers-attr': {
          impact: 'serious',
          messages: {
            pass: 'The headers attribute is exclusively used to refer to other cells in the table',
            incomplete: 'The headers attribute is empty',
            fail: 'The headers attribute is not exclusively used to refer to other cells in the table'
          }
        },
        'th-has-data-cells': {
          impact: 'serious',
          messages: {
            pass: 'All table header cells refer to data cells',
            fail: 'Not all table header cells refer to data cells',
            incomplete: 'Table data cells are missing or empty'
          }
        },
        description: {
          impact: 'critical',
          messages: {
            pass: 'The multimedia element has an audio description track',
            incomplete: 'Check that audio description is available for the element'
          }
        }
      },
      failureSummaries: {
        any: {
          failureMessage: function anonymous(it) {
            var out = 'Fix any of the following:';
            var arr1 = it;
            if (arr1) {
              var value, i1 = -1, l1 = arr1.length - 1;
              while (i1 < l1) {
                value = arr1[i1 += 1];
                out += '\n  ' + value.split('\n').join('\n  ');
              }
            }
            return out;
          }
        },
        none: {
          failureMessage: function anonymous(it) {
            var out = 'Fix all of the following:';
            var arr1 = it;
            if (arr1) {
              var value, i1 = -1, l1 = arr1.length - 1;
              while (i1 < l1) {
                value = arr1[i1 += 1];
                out += '\n  ' + value.split('\n').join('\n  ');
              }
            }
            return out;
          }
        }
      },
      incompleteFallbackMessage: {}
    },
    rules: [ {
      id: 'accesskeys',
      selector: '[accesskey]',
      excludeHidden: false,
      tags: [ 'best-practice', 'cat.keyboard' ],
      all: [],
      any: [],
      none: [ 'accesskeys' ]
    }, {
      id: 'area-alt',
      selector: 'map area[href]',
      excludeHidden: false,
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag111', 'wcag244', 'wcag412', 'section508', 'section508.22.a' ],
      all: [],
      any: [ 'non-empty-alt', 'non-empty-title', 'aria-label', 'aria-labelledby' ],
      none: []
    }, {
      id: 'aria-allowed-attr',
      matches: function matches(node, virtualNode, context) {
        var aria = /^aria-/;
        if (node.hasAttributes()) {
          var attrs = axe.utils.getNodeAttributes(node);
          for (var i = 0, l = attrs.length; i < l; i++) {
            if (aria.test(attrs[i].name)) {
              return true;
            }
          }
        }
        return false;
      },
      tags: [ 'cat.aria', 'wcag2a', 'wcag412' ],
      all: [],
      any: [ 'aria-allowed-attr' ],
      none: [ 'aria-unsupported-attr' ]
    }, {
      id: 'aria-allowed-role',
      excludeHidden: false,
      selector: '[role]',
      matches: function matches(node, virtualNode, context) {
        return axe.commons.aria.getRole(node, {
          noImplicit: true,
          dpub: true,
          fallback: true
        }) !== null;
      },
      tags: [ 'cat.aria', 'best-practice' ],
      all: [],
      any: [ {
        options: {
          allowImplicit: true,
          ignoredTags: []
        },
        id: 'aria-allowed-role'
      } ],
      none: []
    }, {
      id: 'aria-dpub-role-fallback',
      selector: '[role]',
      matches: function matches(node, virtualNode, context) {
        var role = node.getAttribute('role');
        return [ 'doc-backlink', 'doc-biblioentry', 'doc-biblioref', 'doc-cover', 'doc-endnote', 'doc-glossref', 'doc-noteref' ].includes(role);
      },
      tags: [ 'cat.aria', 'wcag2a', 'wcag131', 'deprecated' ],
      enabled: false,
      all: [ 'implicit-role-fallback' ],
      any: [],
      none: []
    }, {
      id: 'aria-hidden-body',
      selector: 'body',
      excludeHidden: false,
      tags: [ 'cat.aria', 'wcag2a', 'wcag412' ],
      all: [],
      any: [ 'aria-hidden-body' ],
      none: []
    }, {
      id: 'aria-hidden-focus',
      selector: '[aria-hidden="true"]',
      matches: function matches(node, virtualNode, context) {
        var getComposedParent = axe.commons.dom.getComposedParent;
        function shouldMatchElement(el) {
          if (!el) {
            return true;
          }
          if (el.getAttribute('aria-hidden') === 'true') {
            return false;
          }
          return shouldMatchElement(getComposedParent(el));
        }
        return shouldMatchElement(getComposedParent(node));
      },
      excludeHidden: false,
      tags: [ 'cat.name-role-value', 'wcag2a', 'wcag412', 'wcag131' ],
      all: [ 'focusable-modal-open', 'focusable-disabled', 'focusable-not-tabbable' ],
      any: [],
      none: []
    }, {
      id: 'aria-input-field-name',
      selector: '[role="combobox"], [role="listbox"], [role="searchbox"], [role="slider"], [role="spinbutton"], [role="textbox"]',
      matches: function matches(node, virtualNode, context) {
        var aria = axe.commons.aria;
        var nodeName = node.nodeName.toUpperCase();
        var role = aria.getRole(node, {
          noImplicit: true
        });
        if (nodeName === 'AREA' && !!node.getAttribute('href')) {
          return false;
        }
        if ([ 'INPUT', 'SELECT', 'TEXTAREA' ].includes(nodeName)) {
          return false;
        }
        if (nodeName === 'IMG' || role === 'img' && nodeName !== 'SVG') {
          return false;
        }
        if (nodeName === 'BUTTON' || role === 'button') {
          return false;
        }
        if (role === 'combobox' && axe.utils.querySelectorAll(virtualNode, 'input:not([type="hidden"])').length) {
          return false;
        }
        return true;
      },
      tags: [ 'wcag2a', 'wcag412' ],
      all: [],
      any: [ 'aria-label', 'aria-labelledby', 'non-empty-title' ],
      none: [ 'no-implicit-explicit-label' ]
    }, {
      id: 'aria-required-attr',
      selector: '[role]',
      tags: [ 'cat.aria', 'wcag2a', 'wcag412' ],
      all: [],
      any: [ 'aria-required-attr' ],
      none: []
    }, {
      id: 'aria-required-children',
      selector: '[role]',
      tags: [ 'cat.aria', 'wcag2a', 'wcag131' ],
      all: [],
      any: [ {
        options: {
          reviewEmpty: [ 'doc-bibliography', 'doc-endnotes', 'grid', 'list', 'listbox', 'table', 'tablist', 'tree', 'treegrid', 'rowgroup' ]
        },
        id: 'aria-required-children'
      } ],
      none: []
    }, {
      id: 'aria-required-parent',
      selector: '[role]',
      tags: [ 'cat.aria', 'wcag2a', 'wcag131' ],
      all: [],
      any: [ 'aria-required-parent' ],
      none: []
    }, {
      id: 'aria-roledescription',
      selector: '[aria-roledescription]',
      tags: [ 'cat.aria', 'wcag2a', 'wcag412' ],
      all: [],
      any: [ {
        options: {
          supportedRoles: [ 'button', 'img', 'checkbox', 'radio', 'combobox', 'menuitemcheckbox', 'menuitemradio' ]
        },
        id: 'aria-roledescription'
      } ],
      none: []
    }, {
      id: 'aria-roles',
      selector: '[role]',
      matches: function matches(node, virtualNode, context) {
        if (!virtualNode.hasAttr('role')) {
          return false;
        }
        if (!virtualNode.attr('role').trim()) {
          return false;
        }
        return true;
      },
      tags: [ 'cat.aria', 'wcag2a', 'wcag412' ],
      all: [],
      any: [],
      none: [ 'fallbackrole', 'invalidrole', 'abstractrole', 'unsupportedrole' ]
    }, {
      id: 'aria-toggle-field-name',
      selector: '[role="checkbox"], [role="menuitemcheckbox"], [role="menuitemradio"], [role="radio"], [role="switch"]',
      matches: function matches(node, virtualNode, context) {
        var aria = axe.commons.aria;
        var nodeName = node.nodeName.toUpperCase();
        var role = aria.getRole(node, {
          noImplicit: true
        });
        if (nodeName === 'AREA' && !!node.getAttribute('href')) {
          return false;
        }
        if ([ 'INPUT', 'SELECT', 'TEXTAREA' ].includes(nodeName)) {
          return false;
        }
        if (nodeName === 'IMG' || role === 'img' && nodeName !== 'SVG') {
          return false;
        }
        if (nodeName === 'BUTTON' || role === 'button') {
          return false;
        }
        if (role === 'combobox' && axe.utils.querySelectorAll(virtualNode, 'input:not([type="hidden"])').length) {
          return false;
        }
        return true;
      },
      tags: [ 'wcag2a', 'wcag412' ],
      all: [],
      any: [ 'aria-label', 'aria-labelledby', 'non-empty-title', 'has-visible-text' ],
      none: [ 'no-implicit-explicit-label' ]
    }, {
      id: 'aria-valid-attr-value',
      matches: function matches(node, virtualNode, context) {
        var aria = /^aria-/;
        if (node.hasAttributes()) {
          var attrs = axe.utils.getNodeAttributes(node);
          for (var i = 0, l = attrs.length; i < l; i++) {
            if (aria.test(attrs[i].name)) {
              return true;
            }
          }
        }
        return false;
      },
      tags: [ 'cat.aria', 'wcag2a', 'wcag412' ],
      all: [ {
        options: [],
        id: 'aria-valid-attr-value'
      }, 'aria-errormessage' ],
      any: [],
      none: []
    }, {
      id: 'aria-valid-attr',
      matches: function matches(node, virtualNode, context) {
        var aria = /^aria-/;
        if (node.hasAttributes()) {
          var attrs = axe.utils.getNodeAttributes(node);
          for (var i = 0, l = attrs.length; i < l; i++) {
            if (aria.test(attrs[i].name)) {
              return true;
            }
          }
        }
        return false;
      },
      tags: [ 'cat.aria', 'wcag2a', 'wcag412' ],
      all: [],
      any: [ {
        options: [],
        id: 'aria-valid-attr'
      } ],
      none: []
    }, {
      id: 'audio-caption',
      selector: 'audio',
      enabled: false,
      excludeHidden: false,
      tags: [ 'cat.time-and-media', 'wcag2a', 'wcag121', 'section508', 'section508.22.a' ],
      all: [],
      any: [],
      none: [ 'caption' ]
    }, {
      id: 'autocomplete-valid',
      matches: function matches(node, virtualNode, context) {
        var _axe$commons = axe.commons, text = _axe$commons.text, aria = _axe$commons.aria, dom = _axe$commons.dom;
        var autocomplete = virtualNode.attr('autocomplete');
        if (!autocomplete || text.sanitize(autocomplete) === '') {
          return false;
        }
        var nodeName = virtualNode.props.nodeName;
        if ([ 'textarea', 'input', 'select' ].includes(nodeName) === false) {
          return false;
        }
        var excludedInputTypes = [ 'submit', 'reset', 'button', 'hidden' ];
        if (nodeName === 'input' && excludedInputTypes.includes(virtualNode.props.type)) {
          return false;
        }
        var ariaDisabled = virtualNode.attr('aria-disabled') || 'false';
        if (virtualNode.hasAttr('disabled') || ariaDisabled.toLowerCase() === 'true') {
          return false;
        }
        var role = virtualNode.attr('role');
        var tabIndex = virtualNode.attr('tabindex');
        if (tabIndex === '-1' && role) {
          var roleDef = aria.lookupTable.role[role];
          if (roleDef === undefined || roleDef.type !== 'widget') {
            return false;
          }
        }
        if (tabIndex === '-1' && virtualNode.actualNode && !dom.isVisible(virtualNode.actualNode, false) && !dom.isVisible(virtualNode.actualNode, true)) {
          return false;
        }
        return true;
      },
      tags: [ 'cat.forms', 'wcag21aa', 'wcag135' ],
      all: [ 'autocomplete-valid', 'autocomplete-appropriate' ],
      any: [],
      none: []
    }, {
      id: 'avoid-inline-spacing',
      selector: '[style]',
      tags: [ 'wcag21aa', 'wcag1412' ],
      all: [ 'avoid-inline-spacing' ],
      any: [],
      none: []
    }, {
      id: 'blink',
      selector: 'blink',
      excludeHidden: false,
      tags: [ 'cat.time-and-media', 'wcag2a', 'wcag222', 'section508', 'section508.22.j' ],
      all: [],
      any: [],
      none: [ 'is-on-screen' ]
    }, {
      id: 'button-name',
      selector: 'button, [role="button"]:not(input)',
      tags: [ 'cat.name-role-value', 'wcag2a', 'wcag412', 'section508', 'section508.22.a' ],
      all: [],
      any: [ 'button-has-visible-text', 'aria-label', 'aria-labelledby', 'role-presentation', 'role-none', 'non-empty-title' ],
      none: []
    }, {
      id: 'bypass',
      selector: 'html',
      pageLevel: true,
      matches: function matches(node, virtualNode, context) {
        return !!node.querySelector('a[href]');
      },
      tags: [ 'cat.keyboard', 'wcag2a', 'wcag241', 'section508', 'section508.22.o' ],
      all: [],
      any: [ 'internal-link-present', 'header-present', 'landmark' ],
      none: []
    }, {
      id: 'checkboxgroup',
      selector: 'input[type=checkbox][name]',
      tags: [ 'cat.forms', 'best-practice', 'deprecated' ],
      enabled: false,
      all: [],
      any: [ 'group-labelledby', 'fieldset' ],
      none: []
    }, {
      id: 'color-contrast',
      matches: function matches(node, virtualNode, context) {
        var nodeName = node.nodeName.toUpperCase();
        var nodeType = node.type;
        if (node.getAttribute('aria-disabled') === 'true' || axe.commons.dom.findUpVirtual(virtualNode, '[aria-disabled="true"]')) {
          return false;
        }
        var formElements = [ 'INPUT', 'SELECT', 'TEXTAREA' ];
        if (formElements.includes(nodeName)) {
          var style = window.getComputedStyle(node);
          var textIndent = parseInt(style.getPropertyValue('text-indent'), 10);
          if (textIndent) {
            var rect = node.getBoundingClientRect();
            rect = {
              top: rect.top,
              bottom: rect.bottom,
              left: rect.left + textIndent,
              right: rect.right + textIndent
            };
            if (!axe.commons.dom.visuallyOverlaps(rect, node)) {
              return false;
            }
          }
        }
        if (nodeName === 'INPUT') {
          return [ 'hidden', 'range', 'color', 'checkbox', 'radio', 'image' ].indexOf(nodeType) === -1 && !node.disabled;
        }
        if (nodeName === 'SELECT') {
          return !!node.options.length && !node.disabled;
        }
        if (nodeName === 'TEXTAREA') {
          return !node.disabled;
        }
        if (nodeName === 'OPTION') {
          return false;
        }
        if (nodeName === 'BUTTON' && node.disabled || axe.commons.dom.findUpVirtual(virtualNode, 'button[disabled]')) {
          return false;
        }
        if (nodeName === 'FIELDSET' && node.disabled || axe.commons.dom.findUpVirtual(virtualNode, 'fieldset[disabled]')) {
          return false;
        }
        var nodeParentLabel = axe.commons.dom.findUpVirtual(virtualNode, 'label');
        if (nodeName === 'LABEL' || nodeParentLabel) {
          var relevantNode = node;
          var relevantVirtualNode = virtualNode;
          if (nodeParentLabel) {
            relevantNode = nodeParentLabel;
            relevantVirtualNode = axe.utils.getNodeFromTree(nodeParentLabel);
          }
          var doc = axe.commons.dom.getRootNode(relevantNode);
          var candidate = relevantNode.htmlFor && doc.getElementById(relevantNode.htmlFor);
          var candidateVirtualNode = axe.utils.getNodeFromTree(candidate);
          if (candidate && (candidate.disabled || candidate.getAttribute('aria-disabled') === 'true' || axe.commons.dom.findUpVirtual(candidateVirtualNode, '[aria-disabled="true"]'))) {
            return false;
          }
          candidate = axe.utils.querySelectorAll(relevantVirtualNode, 'input:not([type="hidden"]):not([type="image"])' + ':not([type="button"]):not([type="submit"]):not([type="reset"]), select, textarea');
          if (candidate.length && candidate[0].actualNode.disabled) {
            return false;
          }
        }
        if (node.getAttribute('id')) {
          var id = axe.utils.escapeSelector(node.getAttribute('id'));
          var _doc = axe.commons.dom.getRootNode(node);
          var _candidate = _doc.querySelector('[aria-labelledby~=' + id + ']');
          if (_candidate && _candidate.disabled) {
            return false;
          }
        }
        var visibleText = axe.commons.text.visibleVirtual(virtualNode, false, true);
        if (visibleText === '' || axe.commons.text.removeUnicode(visibleText, {
          emoji: true,
          nonBmp: false,
          punctuations: true
        }) === '') {
          return false;
        }
        var range = document.createRange();
        var childNodes = virtualNode.children;
        var length = childNodes.length;
        var child = null;
        var index = 0;
        for (index = 0; index < length; index++) {
          child = childNodes[index];
          if (child.actualNode.nodeType === 3 && axe.commons.text.sanitize(child.actualNode.nodeValue) !== '') {
            range.selectNodeContents(child.actualNode);
          }
        }
        var rects = range.getClientRects();
        length = rects.length;
        for (index = 0; index < length; index++) {
          if (axe.commons.dom.visuallyOverlaps(rects[index], node)) {
            return true;
          }
        }
        return false;
      },
      excludeHidden: false,
      tags: [ 'cat.color', 'wcag2aa', 'wcag143' ],
      all: [],
      any: [ {
        options: {
          noScroll: false,
          ignoreUnicode: true,
          ignoreLength: false
        },
        id: 'color-contrast'
      } ],
      none: []
    }, {
      id: 'css-orientation-lock',
      selector: 'html',
      tags: [ 'cat.structure', 'wcag134', 'wcag21aa', 'experimental' ],
      all: [ {
        options: {
          degreeThreshold: 2
        },
        id: 'css-orientation-lock'
      } ],
      any: [],
      none: [],
      preload: true
    }, {
      id: 'definition-list',
      selector: 'dl',
      matches: function matches(node, virtualNode, context) {
        return !node.getAttribute('role');
      },
      tags: [ 'cat.structure', 'wcag2a', 'wcag131' ],
      all: [],
      any: [],
      none: [ 'structured-dlitems', 'only-dlitems' ]
    }, {
      id: 'dlitem',
      selector: 'dd, dt',
      matches: function matches(node, virtualNode, context) {
        return !node.getAttribute('role');
      },
      tags: [ 'cat.structure', 'wcag2a', 'wcag131' ],
      all: [],
      any: [ 'dlitem' ],
      none: []
    }, {
      id: 'document-title',
      selector: 'html',
      matches: function matches(node, virtualNode, context) {
        return node.ownerDocument.defaultView.self === node.ownerDocument.defaultView.top;
      },
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag242' ],
      all: [],
      any: [ 'doc-has-title' ],
      none: []
    }, {
      id: 'duplicate-id-active',
      selector: '[id]',
      matches: function matches(node, virtualNode, context) {
        var _axe$commons2 = axe.commons, dom = _axe$commons2.dom, aria = _axe$commons2.aria;
        var id = node.getAttribute('id').trim();
        var idSelector = '*[id="'.concat(axe.utils.escapeSelector(id), '"]');
        var idMatchingElms = Array.from(dom.getRootNode(node).querySelectorAll(idSelector));
        return !aria.isAccessibleRef(node) && idMatchingElms.some(dom.isFocusable);
      },
      excludeHidden: false,
      tags: [ 'cat.parsing', 'wcag2a', 'wcag411' ],
      all: [],
      any: [ 'duplicate-id-active' ],
      none: []
    }, {
      id: 'duplicate-id-aria',
      selector: '[id]',
      matches: function matches(node, virtualNode, context) {
        return axe.commons.aria.isAccessibleRef(node);
      },
      excludeHidden: false,
      tags: [ 'cat.parsing', 'wcag2a', 'wcag411' ],
      all: [],
      any: [ 'duplicate-id-aria' ],
      none: []
    }, {
      id: 'duplicate-id',
      selector: '[id]',
      matches: function matches(node, virtualNode, context) {
        var _axe$commons3 = axe.commons, dom = _axe$commons3.dom, aria = _axe$commons3.aria;
        var id = node.getAttribute('id').trim();
        var idSelector = '*[id="'.concat(axe.utils.escapeSelector(id), '"]');
        var idMatchingElms = Array.from(dom.getRootNode(node).querySelectorAll(idSelector));
        return !aria.isAccessibleRef(node) && idMatchingElms.every(function(elm) {
          return !dom.isFocusable(elm);
        });
      },
      excludeHidden: false,
      tags: [ 'cat.parsing', 'wcag2a', 'wcag411' ],
      all: [],
      any: [ 'duplicate-id' ],
      none: []
    }, {
      id: 'empty-heading',
      selector: 'h1, h2, h3, h4, h5, h6, [role="heading"]',
      matches: function matches(node, virtualNode, context) {
        var explicitRoles;
        if (node.hasAttribute('role')) {
          explicitRoles = node.getAttribute('role').split(/\s+/i).filter(axe.commons.aria.isValidRole);
        }
        if (explicitRoles && explicitRoles.length > 0) {
          return explicitRoles.includes('heading');
        } else {
          return axe.commons.aria.implicitRole(node) === 'heading';
        }
      },
      tags: [ 'cat.name-role-value', 'best-practice' ],
      all: [],
      any: [ 'has-visible-text' ],
      none: []
    }, {
      id: 'focus-order-semantics',
      selector: 'div, h1, h2, h3, h4, h5, h6, [role=heading], p, span',
      matches: function matches(node, virtualNode, context) {
        return axe.commons.dom.insertedIntoFocusOrder(node);
      },
      tags: [ 'cat.keyboard', 'best-practice', 'experimental' ],
      all: [],
      any: [ {
        options: [],
        id: 'has-widget-role'
      }, {
        options: [],
        id: 'valid-scrollable-semantics'
      } ],
      none: []
    }, {
      id: 'form-field-multiple-labels',
      selector: 'input, select, textarea',
      matches: function matches(node, virtualNode, context) {
        if (node.nodeName.toLowerCase() !== 'input' || node.hasAttribute('type') === false) {
          return true;
        }
        var type = node.getAttribute('type').toLowerCase();
        return [ 'hidden', 'image', 'button', 'submit', 'reset' ].includes(type) === false;
      },
      tags: [ 'cat.forms', 'wcag2a', 'wcag332' ],
      all: [],
      any: [],
      none: [ 'multiple-label' ]
    }, {
      id: 'frame-tested',
      selector: 'frame, iframe',
      tags: [ 'cat.structure', 'review-item', 'best-practice' ],
      all: [ {
        options: {
          isViolation: false
        },
        id: 'frame-tested'
      } ],
      any: [],
      none: []
    }, {
      id: 'frame-title-unique',
      selector: 'frame[title], iframe[title]',
      matches: function matches(node, virtualNode, context) {
        var title = node.getAttribute('title');
        return !!(title ? axe.commons.text.sanitize(title).trim() : '');
      },
      tags: [ 'cat.text-alternatives', 'best-practice' ],
      all: [],
      any: [],
      none: [ 'unique-frame-title' ]
    }, {
      id: 'frame-title',
      selector: 'frame, iframe',
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag241', 'wcag412', 'section508', 'section508.22.i' ],
      all: [],
      any: [ 'aria-label', 'aria-labelledby', 'non-empty-title', 'role-presentation', 'role-none' ],
      none: []
    }, {
      id: 'heading-order',
      selector: 'h1, h2, h3, h4, h5, h6, [role=heading]',
      matches: function matches(node, virtualNode, context) {
        var explicitRoles;
        if (node.hasAttribute('role')) {
          explicitRoles = node.getAttribute('role').split(/\s+/i).filter(axe.commons.aria.isValidRole);
        }
        if (explicitRoles && explicitRoles.length > 0) {
          return explicitRoles.includes('heading');
        } else {
          return axe.commons.aria.implicitRole(node) === 'heading';
        }
      },
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [],
      any: [ 'heading-order' ],
      none: []
    }, {
      id: 'hidden-content',
      selector: '*',
      excludeHidden: false,
      tags: [ 'cat.structure', 'experimental', 'review-item', 'best-practice' ],
      all: [],
      any: [ 'hidden-content' ],
      none: []
    }, {
      id: 'html-has-lang',
      selector: 'html',
      matches: function matches(node, virtualNode, context) {
        return node.ownerDocument.defaultView.self === node.ownerDocument.defaultView.top;
      },
      tags: [ 'cat.language', 'wcag2a', 'wcag311' ],
      all: [],
      any: [ 'has-lang' ],
      none: []
    }, {
      id: 'html-lang-valid',
      selector: 'html[lang], html[xml\\:lang]',
      tags: [ 'cat.language', 'wcag2a', 'wcag311' ],
      all: [],
      any: [],
      none: [ 'valid-lang' ]
    }, {
      id: 'html-xml-lang-mismatch',
      selector: 'html[lang][xml\\:lang]',
      matches: function matches(node, virtualNode, context) {
        var getBaseLang = axe.utils.getBaseLang;
        var primaryLangValue = getBaseLang(node.getAttribute('lang'));
        var primaryXmlLangValue = getBaseLang(node.getAttribute('xml:lang'));
        return axe.utils.validLangs().includes(primaryLangValue) && axe.utils.validLangs().includes(primaryXmlLangValue);
      },
      tags: [ 'cat.language', 'wcag2a', 'wcag311' ],
      all: [ 'xml-lang-mismatch' ],
      any: [],
      none: []
    }, {
      id: 'identical-links-same-purpose',
      selector: 'a[href], area[href], [role="link"]',
      excludeHidden: false,
      matches: function matches(node, virtualNode, context) {
        var _axe$commons4 = axe.commons, aria = _axe$commons4.aria, text = _axe$commons4.text;
        var hasAccName = !!text.accessibleTextVirtual(virtualNode);
        if (!hasAccName) {
          return false;
        }
        var role = aria.getRole(node);
        if (role && role !== 'link') {
          return false;
        }
        return true;
      },
      tags: [ 'wcag2aaa', 'wcag249', 'best-practice' ],
      all: [ 'identical-links-same-purpose' ],
      any: [],
      none: []
    }, {
      id: 'image-alt',
      selector: 'img',
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag111', 'section508', 'section508.22.a' ],
      all: [],
      any: [ 'has-alt', 'aria-label', 'aria-labelledby', 'non-empty-title', 'role-presentation', 'role-none' ],
      none: [ 'alt-space-value' ]
    }, {
      id: 'image-redundant-alt',
      selector: 'img',
      tags: [ 'cat.text-alternatives', 'best-practice' ],
      all: [],
      any: [],
      none: [ 'duplicate-img-label' ]
    }, {
      id: 'input-button-name',
      selector: 'input[type="button"], input[type="submit"], input[type="reset"]',
      tags: [ 'cat.name-role-value', 'wcag2a', 'wcag412', 'section508', 'section508.22.a' ],
      all: [],
      any: [ 'non-empty-if-present', 'non-empty-value', 'aria-label', 'aria-labelledby', 'role-presentation', 'role-none', 'non-empty-title' ],
      none: []
    }, {
      id: 'input-image-alt',
      selector: 'input[type="image"]',
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag111', 'section508', 'section508.22.a' ],
      all: [],
      any: [ 'non-empty-alt', 'aria-label', 'aria-labelledby', 'non-empty-title' ],
      none: []
    }, {
      id: 'label-content-name-mismatch',
      matches: function matches(node, virtualNode, context) {
        var _axe$commons5 = axe.commons, aria = _axe$commons5.aria, text = _axe$commons5.text;
        var role = aria.getRole(node);
        if (!role) {
          return false;
        }
        var widgetRoles = Object.keys(aria.lookupTable.role).filter(function(key) {
          return aria.lookupTable.role[key].type === 'widget';
        });
        var isWidgetType = widgetRoles.includes(role);
        if (!isWidgetType) {
          return false;
        }
        var rolesWithNameFromContents = aria.getRolesWithNameFromContents();
        if (!rolesWithNameFromContents.includes(role)) {
          return false;
        }
        if (!text.sanitize(aria.arialabelText(virtualNode)) && !text.sanitize(aria.arialabelledbyText(node))) {
          return false;
        }
        if (!text.sanitize(text.visibleVirtual(virtualNode))) {
          return false;
        }
        return true;
      },
      tags: [ 'wcag21a', 'wcag253', 'experimental' ],
      all: [],
      any: [ {
        options: {
          pixelThreshold: .1,
          occuranceThreshold: 3
        },
        id: 'label-content-name-mismatch'
      } ],
      none: []
    }, {
      id: 'label-title-only',
      selector: 'input, select, textarea',
      matches: function matches(node, virtualNode, context) {
        if (node.nodeName.toLowerCase() !== 'input' || node.hasAttribute('type') === false) {
          return true;
        }
        var type = node.getAttribute('type').toLowerCase();
        return [ 'hidden', 'image', 'button', 'submit', 'reset' ].includes(type) === false;
      },
      tags: [ 'cat.forms', 'best-practice' ],
      all: [],
      any: [],
      none: [ 'title-only' ]
    }, {
      id: 'label',
      selector: 'input, select, textarea',
      matches: function matches(node, virtualNode, context) {
        if (node.nodeName.toLowerCase() !== 'input' || node.hasAttribute('type') === false) {
          return true;
        }
        var type = node.getAttribute('type').toLowerCase();
        return [ 'hidden', 'image', 'button', 'submit', 'reset' ].includes(type) === false;
      },
      tags: [ 'cat.forms', 'wcag2a', 'wcag412', 'wcag131', 'section508', 'section508.22.n' ],
      all: [],
      any: [ 'aria-label', 'aria-labelledby', 'implicit-label', 'explicit-label', 'non-empty-title' ],
      none: [ 'help-same-as-label', 'hidden-explicit-label' ]
    }, {
      id: 'landmark-banner-is-top-level',
      selector: 'header:not([role]), [role=banner]',
      matches: function matches(node, virtualNode, context) {
        var nativeScopeFilter = 'article, aside, main, nav, section';
        return node.hasAttribute('role') || !axe.commons.dom.findUpVirtual(virtualNode, nativeScopeFilter);
      },
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [],
      any: [ 'landmark-is-top-level' ],
      none: []
    }, {
      id: 'landmark-complementary-is-top-level',
      selector: 'aside:not([role]), [role=complementary]',
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [],
      any: [ 'landmark-is-top-level' ],
      none: []
    }, {
      id: 'landmark-contentinfo-is-top-level',
      selector: 'footer:not([role]), [role=contentinfo]',
      matches: function matches(node, virtualNode, context) {
        var nativeScopeFilter = 'article, aside, main, nav, section';
        return node.hasAttribute('role') || !axe.commons.dom.findUpVirtual(virtualNode, nativeScopeFilter);
      },
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [],
      any: [ 'landmark-is-top-level' ],
      none: []
    }, {
      id: 'landmark-main-is-top-level',
      selector: 'main:not([role]), [role=main]',
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [],
      any: [ 'landmark-is-top-level' ],
      none: []
    }, {
      id: 'landmark-no-duplicate-banner',
      selector: 'header:not([role]), [role=banner]',
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [],
      any: [ {
        options: {
          selector: 'header:not([role]), [role=banner]',
          nativeScopeFilter: 'article, aside, main, nav, section'
        },
        id: 'page-no-duplicate-banner'
      } ],
      none: []
    }, {
      id: 'landmark-no-duplicate-contentinfo',
      selector: 'footer:not([role]), [role=contentinfo]',
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [],
      any: [ {
        options: {
          selector: 'footer:not([role]), [role=contentinfo]',
          nativeScopeFilter: 'article, aside, main, nav, section'
        },
        id: 'page-no-duplicate-contentinfo'
      } ],
      none: []
    }, {
      id: 'landmark-no-duplicate-main',
      selector: 'main:not([role]), [role=main]',
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [],
      any: [ {
        options: {
          selector: 'main:not([role]), [role=\'main\']'
        },
        id: 'page-no-duplicate-main'
      } ],
      none: []
    }, {
      id: 'landmark-one-main',
      selector: 'html',
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [ {
        options: {
          selector: 'main:not([role]), [role=\'main\']'
        },
        id: 'page-has-main'
      } ],
      any: [],
      none: []
    }, {
      id: 'landmark-unique',
      selector: '[role=banner], [role=complementary], [role=contentinfo], [role=main], [role=navigation], [role=region], [role=search], [role=form], form, footer, header, aside, main, nav, section',
      tags: [ 'cat.semantics', 'best-practice' ],
      matches: function matches(node, virtualNode, context) {
        var excludedParentsForHeaderFooterLandmarks = [ 'article', 'aside', 'main', 'nav', 'section' ].join(',');
        function isHeaderFooterLandmark(headerFooterElement) {
          return !axe.commons.dom.findUpVirtual(headerFooterElement, excludedParentsForHeaderFooterLandmarks);
        }
        function isLandmarkVirtual(virtualNode) {
          var actualNode = virtualNode.actualNode;
          var landmarkRoles = axe.commons.aria.getRolesByType('landmark');
          var role = axe.commons.aria.getRole(actualNode);
          if (!role) {
            return false;
          }
          var nodeName = actualNode.nodeName.toUpperCase();
          if (nodeName === 'HEADER' || nodeName === 'FOOTER') {
            return isHeaderFooterLandmark(virtualNode);
          }
          if (nodeName === 'SECTION' || nodeName === 'FORM') {
            var accessibleText = axe.commons.text.accessibleTextVirtual(virtualNode);
            return !!accessibleText;
          }
          return landmarkRoles.indexOf(role) >= 0 || role === 'region';
        }
        return isLandmarkVirtual(virtualNode) && axe.commons.dom.isVisible(node, true);
      },
      all: [],
      any: [ 'landmark-is-unique' ],
      none: []
    }, {
      id: 'layout-table',
      selector: 'table',
      matches: function matches(node, virtualNode, context) {
        var role = (node.getAttribute('role') || '').toLowerCase();
        return !((role === 'presentation' || role === 'none') && !axe.commons.dom.isFocusable(node)) && !axe.commons.table.isDataTable(node);
      },
      tags: [ 'cat.semantics', 'wcag2a', 'wcag131', 'deprecated' ],
      enabled: false,
      all: [],
      any: [],
      none: [ 'has-th', 'has-caption', 'has-summary' ]
    }, {
      id: 'link-in-text-block',
      selector: 'a[href], [role=link]',
      matches: function matches(node, virtualNode, context) {
        var text = axe.commons.text.sanitize(node.textContent);
        var role = node.getAttribute('role');
        if (role && role !== 'link') {
          return false;
        }
        if (!text) {
          return false;
        }
        if (!axe.commons.dom.isVisible(node, false)) {
          return false;
        }
        return axe.commons.dom.isInTextBlock(node);
      },
      excludeHidden: false,
      tags: [ 'cat.color', 'experimental', 'wcag2a', 'wcag141' ],
      all: [ 'link-in-text-block' ],
      any: [],
      none: []
    }, {
      id: 'link-name',
      selector: 'a[href]:not([role=button]), [role=link]',
      tags: [ 'cat.name-role-value', 'wcag2a', 'wcag412', 'wcag244', 'section508', 'section508.22.a' ],
      all: [],
      any: [ 'has-visible-text', 'aria-label', 'aria-labelledby', 'role-presentation', 'role-none' ],
      none: [ 'focusable-no-name' ]
    }, {
      id: 'list',
      selector: 'ul, ol',
      matches: function matches(node, virtualNode, context) {
        return !node.getAttribute('role');
      },
      tags: [ 'cat.structure', 'wcag2a', 'wcag131' ],
      all: [],
      any: [],
      none: [ 'only-listitems' ]
    }, {
      id: 'listitem',
      selector: 'li',
      matches: function matches(node, virtualNode, context) {
        return !node.getAttribute('role');
      },
      tags: [ 'cat.structure', 'wcag2a', 'wcag131' ],
      all: [],
      any: [ 'listitem' ],
      none: []
    }, {
      id: 'marquee',
      selector: 'marquee',
      excludeHidden: false,
      tags: [ 'cat.parsing', 'wcag2a', 'wcag222' ],
      all: [],
      any: [],
      none: [ 'is-on-screen' ]
    }, {
      id: 'meta-refresh',
      selector: 'meta[http-equiv="refresh"]',
      excludeHidden: false,
      tags: [ 'cat.time-and-media', 'wcag2a', 'wcag2aaa', 'wcag221', 'wcag224', 'wcag325' ],
      all: [],
      any: [ 'meta-refresh' ],
      none: []
    }, {
      id: 'meta-viewport-large',
      selector: 'meta[name="viewport"]',
      excludeHidden: false,
      tags: [ 'cat.sensory-and-visual-cues', 'best-practice' ],
      all: [],
      any: [ {
        options: {
          scaleMinimum: 5,
          lowerBound: 2
        },
        id: 'meta-viewport-large'
      } ],
      none: []
    }, {
      id: 'meta-viewport',
      selector: 'meta[name="viewport"]',
      excludeHidden: false,
      tags: [ 'cat.sensory-and-visual-cues', 'best-practice' ],
      all: [],
      any: [ {
        options: {
          scaleMinimum: 2
        },
        id: 'meta-viewport'
      } ],
      none: []
    }, {
      id: 'no-autoplay-audio',
      excludeHidden: false,
      selector: 'audio[autoplay], video[autoplay]',
      matches: function matches(node, virtualNode, context) {
        if (!node.currentSrc) {
          return false;
        }
        if (node.hasAttribute('paused') || node.hasAttribute('muted')) {
          return false;
        }
        return true;
      },
      tags: [ 'wcag2a', 'wcag142', 'experimental' ],
      preload: true,
      all: [ {
        options: {
          allowedDuration: 3
        },
        id: 'no-autoplay-audio'
      } ],
      any: [],
      none: []
    }, {
      id: 'object-alt',
      selector: 'object',
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag111', 'section508', 'section508.22.a' ],
      all: [],
      any: [ 'has-visible-text', 'aria-label', 'aria-labelledby', 'non-empty-title', 'role-presentation', 'role-none' ],
      none: []
    }, {
      id: 'p-as-heading',
      selector: 'p',
      matches: function matches(node, virtualNode, context) {
        var children = Array.from(node.parentNode.childNodes);
        var nodeText = node.textContent.trim();
        var isSentence = /[.!?:;](?![.!?:;])/g;
        if (nodeText.length === 0 || (nodeText.match(isSentence) || []).length >= 2) {
          return false;
        }
        var siblingsAfter = children.slice(children.indexOf(node) + 1).filter(function(elm) {
          return elm.nodeName.toUpperCase() === 'P' && elm.textContent.trim() !== '';
        });
        return siblingsAfter.length !== 0;
      },
      tags: [ 'cat.semantics', 'wcag2a', 'wcag131', 'experimental' ],
      all: [ {
        options: {
          margins: [ {
            weight: 150,
            italic: true
          }, {
            weight: 150,
            size: 1.15
          }, {
            italic: true,
            size: 1.15
          }, {
            size: 1.4
          } ]
        },
        id: 'p-as-heading'
      } ],
      any: [],
      none: []
    }, {
      id: 'page-has-heading-one',
      selector: 'html',
      tags: [ 'cat.semantics', 'best-practice' ],
      all: [ {
        options: {
          selector: 'h1:not([role]), [role="heading"][aria-level="1"]'
        },
        id: 'page-has-heading-one'
      } ],
      any: [],
      none: []
    }, {
      id: 'radiogroup',
      selector: 'input[type=radio][name]',
      tags: [ 'cat.forms', 'best-practice', 'deprecated' ],
      enabled: false,
      all: [],
      any: [ 'group-labelledby', 'fieldset' ],
      none: []
    }, {
      id: 'region',
      selector: 'body *',
      tags: [ 'cat.keyboard', 'best-practice' ],
      all: [],
      any: [ 'region' ],
      none: []
    }, {
      id: 'role-img-alt',
      selector: '[role=\'img\']:not(img):not(area):not(input):not(object)',
      matches: function matches(node, virtualNode, context) {
        return node.namespaceURI === 'http://www.w3.org/1999/xhtml';
      },
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag111', 'section508', 'section508.22.a' ],
      all: [],
      any: [ 'aria-label', 'aria-labelledby', 'non-empty-title' ],
      none: []
    }, {
      id: 'scope-attr-valid',
      selector: 'td[scope], th[scope]',
      tags: [ 'cat.tables', 'best-practice' ],
      all: [ 'html5-scope', 'scope-value' ],
      any: [],
      none: []
    }, {
      id: 'scrollable-region-focusable',
      matches: function matches(node, virtualNode, context) {
        var querySelectorAll = axe.utils.querySelectorAll;
        var hasContentVirtual = axe.commons.dom.hasContentVirtual;
        if (!!axe.utils.getScroll(node, 13) === false) {
          return false;
        }
        var nodeAndDescendents = querySelectorAll(virtualNode, '*');
        var hasVisibleChildren = nodeAndDescendents.some(function(elm) {
          return hasContentVirtual(elm, true, true);
        });
        if (!hasVisibleChildren) {
          return false;
        }
        return true;
      },
      tags: [ 'wcag2a', 'wcag211' ],
      all: [],
      any: [ 'focusable-content', 'focusable-element' ],
      none: []
    }, {
      id: 'server-side-image-map',
      selector: 'img[ismap]',
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag211', 'section508', 'section508.22.f' ],
      all: [],
      any: [],
      none: [ 'exists' ]
    }, {
      id: 'skip-link',
      selector: 'a[href^="#"], a[href^="/#"]',
      matches: function matches(node, virtualNode, context) {
        return axe.commons.dom.isSkipLink(node) && axe.commons.dom.isOffscreen(node);
      },
      tags: [ 'cat.keyboard', 'best-practice' ],
      all: [],
      any: [ 'skip-link' ],
      none: []
    }, {
      id: 'svg-img-alt',
      selector: '[role="img"], [role="graphics-symbol"], svg[role="graphics-document"]',
      matches: function matches(node, virtualNode, context) {
        return node.namespaceURI === 'http://www.w3.org/2000/svg';
      },
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag111', 'section508', 'section508.22.a' ],
      all: [],
      any: [ 'svg-non-empty-title', 'aria-label', 'aria-labelledby', 'non-empty-title' ],
      none: []
    }, {
      id: 'tabindex',
      selector: '[tabindex]',
      tags: [ 'cat.keyboard', 'best-practice' ],
      all: [],
      any: [ 'tabindex' ],
      none: []
    }, {
      id: 'table-duplicate-name',
      selector: 'table',
      tags: [ 'cat.tables', 'best-practice' ],
      all: [],
      any: [],
      none: [ 'same-caption-summary' ]
    }, {
      id: 'table-fake-caption',
      selector: 'table',
      matches: function matches(node, virtualNode, context) {
        return axe.commons.table.isDataTable(node);
      },
      tags: [ 'cat.tables', 'experimental', 'wcag2a', 'wcag131', 'section508', 'section508.22.g' ],
      all: [ 'caption-faked' ],
      any: [],
      none: []
    }, {
      id: 'td-has-header',
      selector: 'table',
      matches: function matches(node, virtualNode, context) {
        if (axe.commons.table.isDataTable(node)) {
          var tableArray = axe.commons.table.toArray(node);
          return tableArray.length >= 3 && tableArray[0].length >= 3 && tableArray[1].length >= 3 && tableArray[2].length >= 3;
        }
        return false;
      },
      tags: [ 'cat.tables', 'experimental', 'wcag2a', 'wcag131', 'section508', 'section508.22.g' ],
      all: [ 'td-has-header' ],
      any: [],
      none: []
    }, {
      id: 'td-headers-attr',
      selector: 'table',
      tags: [ 'cat.tables', 'wcag2a', 'wcag131', 'section508', 'section508.22.g' ],
      all: [ 'td-headers-attr' ],
      any: [],
      none: []
    }, {
      id: 'th-has-data-cells',
      selector: 'table',
      matches: function matches(node, virtualNode, context) {
        return axe.commons.table.isDataTable(node);
      },
      tags: [ 'cat.tables', 'wcag2a', 'wcag131', 'section508', 'section508.22.g' ],
      all: [ 'th-has-data-cells' ],
      any: [],
      none: []
    }, {
      id: 'valid-lang',
      selector: '[lang], [xml\\:lang]',
      matches: function matches(node, virtualNode, context) {
        return node.nodeName.toLowerCase() !== 'html';
      },
      tags: [ 'cat.language', 'wcag2aa', 'wcag312' ],
      all: [],
      any: [],
      none: [ 'valid-lang' ]
    }, {
      id: 'video-caption',
      selector: 'video',
      excludeHidden: false,
      tags: [ 'cat.text-alternatives', 'wcag2a', 'wcag122', 'section508', 'section508.22.a' ],
      all: [],
      any: [],
      none: [ 'caption' ]
    }, {
      id: 'video-description',
      selector: 'video',
      excludeHidden: false,
      tags: [ 'cat.text-alternatives', 'wcag2aa', 'wcag125', 'section508', 'section508.22.b', 'deprecated' ],
      enabled: false,
      all: [],
      any: [],
      none: [ 'description' ]
    } ],
    checks: [ {
      id: 'abstractrole',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var abstractRoles = axe.utils.tokenList(virtualNode.attr('role')).filter(function(role) {
          return axe.commons.aria.getRoleType(role) === 'abstract';
        });
        if (abstractRoles.length > 0) {
          this.data(abstractRoles);
          return true;
        }
        return false;
      }
    }, {
      id: 'aria-allowed-attr',
      evaluate: function evaluate(node, options, virtualNode, context) {
        options = options || {};
        var invalid = [];
        var attr, attrName, allowed, role = node.getAttribute('role'), attrs = axe.utils.getNodeAttributes(node);
        if (!role) {
          role = axe.commons.aria.implicitRole(node);
        }
        allowed = axe.commons.aria.allowedAttr(role);
        if (Array.isArray(options[role])) {
          allowed = axe.utils.uniqueArray(options[role].concat(allowed));
        }
        if (role && allowed) {
          for (var i = 0, l = attrs.length; i < l; i++) {
            attr = attrs[i];
            attrName = attr.name;
            if (axe.commons.aria.validateAttr(attrName) && !allowed.includes(attrName)) {
              invalid.push(attrName + '="' + attr.nodeValue + '"');
            }
          }
        }
        if (invalid.length) {
          this.data(invalid);
          return false;
        }
        return true;
      }
    }, {
      id: 'aria-allowed-role',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var dom = axe.commons.dom;
        var _ref = options || {}, _ref$allowImplicit = _ref.allowImplicit, allowImplicit = _ref$allowImplicit === void 0 ? true : _ref$allowImplicit, _ref$ignoredTags = _ref.ignoredTags, ignoredTags = _ref$ignoredTags === void 0 ? [] : _ref$ignoredTags;
        var tagName = node.nodeName.toUpperCase();
        if (ignoredTags.map(function(t) {
          return t.toUpperCase();
        }).includes(tagName)) {
          return true;
        }
        var unallowedRoles = axe.commons.aria.getElementUnallowedRoles(node, allowImplicit);
        if (unallowedRoles.length) {
          this.data(unallowedRoles);
          if (!dom.isVisible(node, true)) {
            return undefined;
          }
          return false;
        }
        return true;
      },
      options: {
        allowImplicit: true,
        ignoredTags: []
      }
    }, {
      id: 'aria-hidden-body',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return node.getAttribute('aria-hidden') !== 'true';
      }
    }, {
      id: 'aria-roledescription',
      evaluate: function evaluate(node, options, virtualNode, context) {
        options = options || {};
        var role = axe.commons.aria.getRole(node);
        var supportedRoles = options.supportedRoles || [];
        if (supportedRoles.includes(role)) {
          return true;
        }
        if (role && role !== 'presentation' && role !== 'none') {
          return undefined;
        }
        return false;
      },
      options: {
        supportedRoles: [ 'button', 'img', 'checkbox', 'radio', 'combobox', 'menuitemcheckbox', 'menuitemradio' ]
      }
    }, {
      id: 'aria-errormessage',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons6 = axe.commons, aria = _axe$commons6.aria, dom = _axe$commons6.dom;
        options = Array.isArray(options) ? options : [];
        var attr = node.getAttribute('aria-errormessage');
        var hasAttr = node.hasAttribute('aria-errormessage');
        var doc = dom.getRootNode(node);
        function validateAttrValue(attr) {
          if (attr.trim() === '') {
            return aria.lookupTable.attributes['aria-errormessage'].allowEmpty;
          }
          var idref = attr && doc.getElementById(attr);
          if (idref) {
            return idref.getAttribute('role') === 'alert' || idref.getAttribute('aria-live') === 'assertive' || axe.utils.tokenList(node.getAttribute('aria-describedby') || '').indexOf(attr) > -1;
          }
        }
        if (options.indexOf(attr) === -1 && hasAttr) {
          if (!validateAttrValue(attr)) {
            this.data(axe.utils.tokenList(attr));
            return false;
          }
        }
        return true;
      }
    }, {
      id: 'fallbackrole',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return axe.utils.tokenList(virtualNode.attr('role')).length > 1;
      }
    }, {
      id: 'has-widget-role',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var role = node.getAttribute('role');
        if (role === null) {
          return false;
        }
        var roleType = axe.commons.aria.getRoleType(role);
        return roleType === 'widget' || roleType === 'composite';
      },
      options: []
    }, {
      id: 'implicit-role-fallback',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var role = node.getAttribute('role');
        if (role === null || !axe.commons.aria.isValidRole(role)) {
          return true;
        }
        var roleType = axe.commons.aria.getRoleType(role);
        return axe.commons.aria.implicitRole(node) === roleType;
      },
      deprecated: true
    }, {
      id: 'invalidrole',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var tokenList = axe.utils.tokenList;
        var aria = axe.commons.aria;
        var allRoles = tokenList(virtualNode.attr('role'));
        var allInvalid = allRoles.every(function(role) {
          return !aria.isValidRole(role, {
            allowAbstract: true
          });
        });
        if (allInvalid) {
          this.data(allRoles);
          return true;
        }
        return false;
      }
    }, {
      id: 'no-implicit-explicit-label',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons7 = axe.commons, aria = _axe$commons7.aria, text = _axe$commons7.text;
        var role = aria.getRole(node, {
          noImplicit: true
        });
        this.data(role);
        var labelText = text.sanitize(text.labelText(virtualNode)).toLowerCase();
        var accText = text.sanitize(text.accessibleText(node)).toLowerCase();
        if (!accText && !labelText) {
          return false;
        }
        if (!accText && labelText) {
          return undefined;
        }
        if (!accText.includes(labelText)) {
          return undefined;
        }
        return false;
      }
    }, {
      id: 'aria-required-attr',
      evaluate: function evaluate(node, options, virtualNode, context) {
        options = options || {};
        var missing = [];
        var _axe$commons$forms = axe.commons.forms, isNativeTextbox = _axe$commons$forms.isNativeTextbox, isNativeSelect = _axe$commons$forms.isNativeSelect, isAriaTextbox = _axe$commons$forms.isAriaTextbox, isAriaListbox = _axe$commons$forms.isAriaListbox, isAriaCombobox = _axe$commons$forms.isAriaCombobox, isAriaRange = _axe$commons$forms.isAriaRange;
        var preChecks = {
          'aria-valuenow': function ariaValuenow() {
            return !(isNativeTextbox(node) || isNativeSelect(node) || isAriaTextbox(node) || isAriaListbox(node) || isAriaCombobox(node) || isAriaRange(node) && node.hasAttribute('aria-valuenow'));
          }
        };
        if (node.hasAttributes()) {
          var role = node.getAttribute('role');
          var required = axe.commons.aria.requiredAttr(role);
          if (Array.isArray(options[role])) {
            required = axe.utils.uniqueArray(options[role], required);
          }
          if (role && required) {
            for (var i = 0, l = required.length; i < l; i++) {
              var attr = required[i];
              if (!node.getAttribute(attr) && (preChecks[attr] ? preChecks[attr]() : true)) {
                missing.push(attr);
              }
            }
          }
        }
        if (missing.length) {
          this.data(missing);
          return false;
        }
        return true;
      }
    }, {
      id: 'aria-required-children',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var requiredOwned = axe.commons.aria.requiredOwned;
        var implicitNodes = axe.commons.aria.implicitNodes;
        var matchesSelector = axe.utils.matchesSelector;
        var idrefs = axe.commons.dom.idrefs;
        var hasContentVirtual = axe.commons.dom.hasContentVirtual;
        var reviewEmpty = options && Array.isArray(options.reviewEmpty) ? options.reviewEmpty : [];
        function owns(node, virtualTree, role, ariaOwned) {
          if (node === null) {
            return false;
          }
          var implicit = implicitNodes(role);
          var selector = [ '[role="' + role + '"]' ];
          if (implicit) {
            selector = selector.concat(implicit.map(function(implicitSelector) {
              return implicitSelector + ':not([role])';
            }));
          }
          selector = selector.join(',');
          return ariaOwned ? matchesSelector(node, selector) || !!axe.utils.querySelectorAll(virtualTree, selector)[0] : !!axe.utils.querySelectorAll(virtualTree, selector)[0];
        }
        function ariaOwns(nodes, role) {
          for (var index = 0; index < nodes.length; index++) {
            var _node = nodes[index];
            if (_node === null) {
              continue;
            }
            var virtualTree = axe.utils.getNodeFromTree(_node);
            if (owns(_node, virtualTree, role, true)) {
              return true;
            }
          }
          return false;
        }
        function missingRequiredChildren(node, childRoles, all, role) {
          var missing = [], ownedElements = idrefs(node, 'aria-owns');
          for (var index = 0; index < childRoles.length; index++) {
            var childRole = childRoles[index];
            if (owns(node, virtualNode, childRole) || ariaOwns(ownedElements, childRole)) {
              if (!all) {
                return null;
              }
            } else {
              if (all) {
                missing.push(childRole);
              }
            }
          }
          if (role === 'combobox') {
            var textboxIndex = missing.indexOf('textbox');
            var textTypeInputs = [ 'text', 'search', 'email', 'url', 'tel' ];
            if (textboxIndex >= 0 && node.nodeName.toUpperCase() === 'INPUT' && textTypeInputs.includes(node.type) || owns(node, virtualNode, 'searchbox') || ariaOwns(ownedElements, 'searchbox')) {
              missing.splice(textboxIndex, 1);
            }
            var expandedChildRoles = [ 'listbox', 'tree', 'grid', 'dialog' ];
            var expandedValue = node.getAttribute('aria-expanded');
            var expanded = expandedValue && expandedValue !== 'false';
            var popupRole = (node.getAttribute('aria-haspopup') || 'listbox').toLowerCase();
            for (var _index = 0; _index < expandedChildRoles.length; _index++) {
              var expandedChildRole = expandedChildRoles[_index];
              if (expanded && expandedChildRole === popupRole) {
                continue;
              }
              var missingIndex = missing.indexOf(expandedChildRole);
              if (missingIndex >= 0) {
                missing.splice(missingIndex, 1);
              }
            }
          }
          if (missing.length) {
            return missing;
          }
          if (!all && childRoles.length) {
            return childRoles;
          }
          return null;
        }
        function hasDecendantWithRole(node) {
          return node.children && node.children.some(function(child) {
            var role = axe.commons.aria.getRole(child);
            return ![ 'presentation', 'none', null ].includes(role) || hasDecendantWithRole(child);
          });
        }
        var role = node.getAttribute('role');
        var required = requiredOwned(role);
        if (!required) {
          return true;
        }
        var all = false;
        var childRoles = required.one;
        if (!childRoles) {
          all = true;
          childRoles = required.all;
        }
        var missing = missingRequiredChildren(node, childRoles, all, role);
        if (!missing) {
          return true;
        }
        this.data(missing);
        if (reviewEmpty.includes(role) && !hasContentVirtual(virtualNode, false, true) && !hasDecendantWithRole(virtualNode) && idrefs(node, 'aria-owns').length === 0) {
          return undefined;
        } else {
          return false;
        }
      },
      options: {
        reviewEmpty: [ 'doc-bibliography', 'doc-endnotes', 'grid', 'list', 'listbox', 'table', 'tablist', 'tree', 'treegrid', 'rowgroup' ]
      }
    }, {
      id: 'aria-required-parent',
      evaluate: function evaluate(node, options, virtualNode, context) {
        function getSelector(role) {
          var impliedNative = axe.commons.aria.implicitNodes(role) || [];
          return impliedNative.concat('[role="' + role + '"]').join(',');
        }
        function getMissingContext(virtualNode, requiredContext, includeElement) {
          var index, length, role = virtualNode.actualNode.getAttribute('role'), missing = [];
          if (!requiredContext) {
            requiredContext = axe.commons.aria.requiredContext(role);
          }
          if (!requiredContext) {
            return null;
          }
          for (index = 0, length = requiredContext.length; index < length; index++) {
            if (includeElement && axe.utils.matchesSelector(virtualNode.actualNode, getSelector(requiredContext[index]))) {
              return null;
            }
            if (axe.commons.dom.findUpVirtual(virtualNode, getSelector(requiredContext[index]))) {
              return null;
            } else {
              missing.push(requiredContext[index]);
            }
          }
          return missing;
        }
        function getAriaOwners(element) {
          var owners = [], o = null;
          while (element) {
            if (element.getAttribute('id')) {
              var id = axe.utils.escapeSelector(element.getAttribute('id'));
              var doc = axe.commons.dom.getRootNode(element);
              o = doc.querySelector('[aria-owns~='.concat(id, ']'));
              if (o) {
                owners.push(o);
              }
            }
            element = element.parentElement;
          }
          return owners.length ? owners : null;
        }
        var missingParents = getMissingContext(virtualNode);
        if (!missingParents) {
          return true;
        }
        var owners = getAriaOwners(node);
        if (owners) {
          for (var i = 0, l = owners.length; i < l; i++) {
            missingParents = getMissingContext(axe.utils.getNodeFromTree(owners[i]), missingParents, true);
            if (!missingParents) {
              return true;
            }
          }
        }
        this.data(missingParents);
        return false;
      }
    }, {
      id: 'aria-unsupported-attr',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var nodeName = node.nodeName.toUpperCase();
        var lookupTable = axe.commons.aria.lookupTable;
        var role = axe.commons.aria.getRole(node);
        var unsupportedAttrs = Array.from(axe.utils.getNodeAttributes(node)).filter(function(_ref2) {
          var name = _ref2.name;
          var attribute = lookupTable.attributes[name];
          if (!axe.commons.aria.validateAttr(name)) {
            return false;
          }
          var unsupported = attribute.unsupported;
          if (_typeof(unsupported) !== 'object') {
            return !!unsupported;
          }
          var isException = axe.commons.matches(node, unsupported.exceptions);
          if (!Object.keys(lookupTable.evaluateRoleForElement).includes(nodeName)) {
            return !isException;
          }
          return !lookupTable.evaluateRoleForElement[nodeName]({
            node: node,
            role: role,
            out: isException
          });
        }).map(function(candidate) {
          return candidate.name.toString();
        });
        if (unsupportedAttrs.length) {
          this.data(unsupportedAttrs);
          return true;
        }
        return false;
      }
    }, {
      id: 'unsupportedrole',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return axe.commons.aria.isUnsupportedRole(axe.commons.aria.getRole(node));
      }
    }, {
      id: 'aria-valid-attr-value',
      evaluate: function evaluate(node, options, virtualNode, context) {
        options = Array.isArray(options) ? options : [];
        var needsReview = '';
        var messageKey = '';
        var invalid = [];
        var aria = /^aria-/;
        var attrs = axe.utils.getNodeAttributes(node);
        var skipAttrs = [ 'aria-errormessage' ];
        var preChecks = {
          'aria-controls': function ariaControls() {
            return node.getAttribute('aria-expanded') !== 'false' && node.getAttribute('aria-selected') !== 'false';
          },
          'aria-current': function ariaCurrent() {
            if (!axe.commons.aria.validateAttrValue(node, 'aria-current')) {
              needsReview = 'aria-current="'.concat(node.getAttribute('aria-current'), '"');
              messageKey = 'ariaCurrent';
            }
            return;
          },
          'aria-owns': function ariaOwns() {
            return node.getAttribute('aria-expanded') !== 'false';
          },
          'aria-describedby': function ariaDescribedby() {
            if (!axe.commons.aria.validateAttrValue(node, 'aria-describedby')) {
              needsReview = 'aria-describedby="'.concat(node.getAttribute('aria-describedby'), '"');
              messageKey = 'noId';
            }
            return;
          }
        };
        for (var i = 0, l = attrs.length; i < l; i++) {
          var attr = attrs[i];
          var attrName = attr.name;
          if (!skipAttrs.includes(attrName) && options.indexOf(attrName) === -1 && aria.test(attrName) && (preChecks[attrName] ? preChecks[attrName]() : true) && !axe.commons.aria.validateAttrValue(node, attrName)) {
            invalid.push(''.concat(attrName, '="').concat(attr.nodeValue, '"'));
          }
        }
        if (needsReview) {
          this.data({
            messageKey: messageKey,
            needsReview: needsReview
          });
          return undefined;
        }
        if (invalid.length) {
          this.data(invalid);
          return false;
        }
        return true;
      },
      options: []
    }, {
      id: 'aria-valid-attr',
      evaluate: function evaluate(node, options, virtualNode, context) {
        options = Array.isArray(options) ? options : [];
        var invalid = [], aria = /^aria-/;
        var attr, attrs = axe.utils.getNodeAttributes(node);
        for (var i = 0, l = attrs.length; i < l; i++) {
          attr = attrs[i].name;
          if (options.indexOf(attr) === -1 && aria.test(attr) && !axe.commons.aria.validateAttr(attr)) {
            invalid.push(attr);
          }
        }
        if (invalid.length) {
          this.data(invalid);
          return false;
        }
        return true;
      },
      options: []
    }, {
      id: 'valid-scrollable-semantics',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var VALID_TAG_NAMES_FOR_SCROLLABLE_REGIONS = {
          ARTICLE: true,
          ASIDE: true,
          NAV: true,
          SECTION: true
        };
        var VALID_ROLES_FOR_SCROLLABLE_REGIONS = {
          application: true,
          banner: false,
          complementary: true,
          contentinfo: true,
          form: true,
          main: true,
          navigation: true,
          region: true,
          search: false
        };
        function validScrollableTagName(node) {
          var nodeName = node.nodeName.toUpperCase();
          return VALID_TAG_NAMES_FOR_SCROLLABLE_REGIONS[nodeName] || false;
        }
        function validScrollableRole(node) {
          var role = node.getAttribute('role');
          if (!role) {
            return false;
          }
          return VALID_ROLES_FOR_SCROLLABLE_REGIONS[role.toLowerCase()] || false;
        }
        function validScrollableSemantics(node) {
          return validScrollableRole(node) || validScrollableTagName(node);
        }
        return validScrollableSemantics(node);
      },
      options: []
    }, {
      id: 'color-contrast',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons8 = axe.commons, dom = _axe$commons8.dom, color = _axe$commons8.color, text = _axe$commons8.text;
        if (!dom.isVisible(node, false)) {
          return true;
        }
        var visibleText = text.visibleVirtual(virtualNode, false, true);
        var ignoreUnicode = !!(options || {}).ignoreUnicode;
        var textContainsOnlyUnicode = text.hasUnicode(visibleText, {
          nonBmp: true
        }) && text.sanitize(text.removeUnicode(visibleText, {
          nonBmp: true
        })) === '';
        if (textContainsOnlyUnicode && ignoreUnicode) {
          this.data({
            messageKey: 'nonBmp'
          });
          return undefined;
        }
        var noScroll = !!(options || {}).noScroll;
        var bgNodes = [];
        var bgColor = color.getBackgroundColor(node, bgNodes, noScroll);
        var fgColor = color.getForegroundColor(node, noScroll, bgColor);
        var nodeStyle = window.getComputedStyle(node);
        var fontSize = parseFloat(nodeStyle.getPropertyValue('font-size'));
        var fontWeight = nodeStyle.getPropertyValue('font-weight');
        var bold = parseFloat(fontWeight) >= 700 || fontWeight === 'bold';
        var cr = color.hasValidContrastRatio(bgColor, fgColor, fontSize, bold);
        var truncatedResult = Math.floor(cr.contrastRatio * 100) / 100;
        var missing;
        if (bgColor === null) {
          missing = color.incompleteData.get('bgColor');
        }
        var equalRatio = truncatedResult === 1;
        var shortTextContent = visibleText.length === 1;
        var ignoreLength = !!(options || {}).ignoreLength;
        if (equalRatio) {
          missing = color.incompleteData.set('bgColor', 'equalRatio');
        } else if (shortTextContent && !ignoreLength) {
          missing = 'shortTextContent';
        }
        var data = {
          fgColor: fgColor ? fgColor.toHexString() : undefined,
          bgColor: bgColor ? bgColor.toHexString() : undefined,
          contrastRatio: cr ? truncatedResult : undefined,
          fontSize: ''.concat((fontSize * 72 / 96).toFixed(1), 'pt (').concat(fontSize, 'px)'),
          fontWeight: bold ? 'bold' : 'normal',
          messageKey: missing,
          expectedContrastRatio: cr.expectedContrastRatio + ':1'
        };
        this.data(data);
        if (fgColor === null || bgColor === null || equalRatio || shortTextContent && !ignoreLength && !cr.isValid) {
          missing = null;
          color.incompleteData.clear();
          this.relatedNodes(bgNodes);
          return undefined;
        }
        if (!cr.isValid) {
          this.relatedNodes(bgNodes);
        }
        return cr.isValid;
      },
      options: {
        noScroll: false,
        ignoreUnicode: true,
        ignoreLength: false
      }
    }, {
      id: 'link-in-text-block',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons9 = axe.commons, color = _axe$commons9.color, dom = _axe$commons9.dom;
        function getContrast(color1, color2) {
          var c1lum = color1.getRelativeLuminance();
          var c2lum = color2.getRelativeLuminance();
          return (Math.max(c1lum, c2lum) + .05) / (Math.min(c1lum, c2lum) + .05);
        }
        var blockLike = [ 'block', 'list-item', 'table', 'flex', 'grid', 'inline-block' ];
        function isBlock(elm) {
          var display = window.getComputedStyle(elm).getPropertyValue('display');
          return blockLike.indexOf(display) !== -1 || display.substr(0, 6) === 'table-';
        }
        if (isBlock(node)) {
          return false;
        }
        var parentBlock = dom.getComposedParent(node);
        while (parentBlock.nodeType === 1 && !isBlock(parentBlock)) {
          parentBlock = dom.getComposedParent(parentBlock);
        }
        this.relatedNodes([ parentBlock ]);
        if (color.elementIsDistinct(node, parentBlock)) {
          return true;
        } else {
          var nodeColor, parentColor;
          nodeColor = color.getForegroundColor(node);
          parentColor = color.getForegroundColor(parentBlock);
          if (!nodeColor || !parentColor) {
            return undefined;
          }
          var contrast = getContrast(nodeColor, parentColor);
          if (contrast === 1) {
            return true;
          } else if (contrast >= 3) {
            axe.commons.color.incompleteData.set('fgColor', 'bgContrast');
            this.data({
              messageKey: axe.commons.color.incompleteData.get('fgColor')
            });
            axe.commons.color.incompleteData.clear();
            return undefined;
          }
          nodeColor = color.getBackgroundColor(node);
          parentColor = color.getBackgroundColor(parentBlock);
          if (!nodeColor || !parentColor || getContrast(nodeColor, parentColor) >= 3) {
            var reason;
            if (!nodeColor || !parentColor) {
              reason = axe.commons.color.incompleteData.get('bgColor');
            } else {
              reason = 'bgContrast';
            }
            axe.commons.color.incompleteData.set('fgColor', reason);
            this.data({
              messageKey: axe.commons.color.incompleteData.get('fgColor')
            });
            axe.commons.color.incompleteData.clear();
            return undefined;
          }
        }
        return false;
      }
    }, {
      id: 'autocomplete-appropriate',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (virtualNode.props.nodeName !== 'input') {
          return true;
        }
        var number = [ 'text', 'search', 'number' ];
        var url = [ 'text', 'search', 'url' ];
        var allowedTypesMap = {
          bday: [ 'text', 'search', 'date' ],
          email: [ 'text', 'search', 'email' ],
          'cc-exp': [ 'text', 'search', 'month' ],
          'street-address': [ 'text' ],
          tel: [ 'text', 'search', 'tel' ],
          'cc-exp-month': number,
          'cc-exp-year': number,
          'transaction-amount': number,
          'bday-day': number,
          'bday-month': number,
          'bday-year': number,
          'new-password': [ 'text', 'search', 'password' ],
          'current-password': [ 'text', 'search', 'password' ],
          url: url,
          photo: url,
          impp: url
        };
        if (_typeof(options) === 'object') {
          Object.keys(options).forEach(function(key) {
            if (!allowedTypesMap[key]) {
              allowedTypesMap[key] = [];
            }
            allowedTypesMap[key] = allowedTypesMap[key].concat(options[key]);
          });
        }
        var autocomplete = virtualNode.attr('autocomplete');
        var autocompleteTerms = autocomplete.split(/\s+/g).map(function(term) {
          return term.toLowerCase();
        });
        var purposeTerm = autocompleteTerms[autocompleteTerms.length - 1];
        if (axe.commons.text.autocomplete.stateTerms.includes(purposeTerm)) {
          return true;
        }
        var allowedTypes = allowedTypesMap[purposeTerm];
        var type = virtualNode.hasAttr('type') ? axe.commons.text.sanitize(virtualNode.attr('type')).toLowerCase() : 'text';
        type = axe.utils.validInputTypes().includes(type) ? type : 'text';
        if (typeof allowedTypes === 'undefined') {
          return type === 'text';
        }
        return allowedTypes.includes(type);
      }
    }, {
      id: 'autocomplete-valid',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var autocomplete = virtualNode.attr('autocomplete') || '';
        return axe.commons.text.isValidAutocomplete(autocomplete, options);
      }
    }, {
      id: 'fieldset',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var failureCode, self = this;
        function getUnrelatedElements(parent, name) {
          return axe.utils.toArray(parent.querySelectorAll('select,textarea,button,input:not([name="' + name + '"]):not([type="hidden"])'));
        }
        function checkFieldset(group, name) {
          var firstNode = group.firstElementChild;
          if (!firstNode || firstNode.nodeName.toUpperCase() !== 'LEGEND') {
            self.relatedNodes([ group ]);
            failureCode = 'no-legend';
            return false;
          }
          if (!axe.commons.text.accessibleText(firstNode)) {
            self.relatedNodes([ firstNode ]);
            failureCode = 'empty-legend';
            return false;
          }
          var otherElements = getUnrelatedElements(group, name);
          if (otherElements.length) {
            self.relatedNodes(otherElements);
            failureCode = 'mixed-inputs';
            return false;
          }
          return true;
        }
        function checkARIAGroup(group, name) {
          var hasLabelledByText = axe.commons.dom.idrefs(group, 'aria-labelledby').some(function(element) {
            return element && axe.commons.text.accessibleText(element);
          });
          var ariaLabel = group.getAttribute('aria-label');
          if (!hasLabelledByText && !(ariaLabel && axe.commons.text.sanitize(ariaLabel))) {
            self.relatedNodes(group);
            failureCode = 'no-group-label';
            return false;
          }
          var otherElements = getUnrelatedElements(group, name);
          if (otherElements.length) {
            self.relatedNodes(otherElements);
            failureCode = 'group-mixed-inputs';
            return false;
          }
          return true;
        }
        function spliceCurrentNode(nodes, current) {
          return axe.utils.toArray(nodes).filter(function(candidate) {
            return candidate !== current;
          });
        }
        function runCheck(virtualNode) {
          var name = axe.utils.escapeSelector(virtualNode.actualNode.name);
          var root = axe.commons.dom.getRootNode(virtualNode.actualNode);
          var matchingNodes = root.querySelectorAll('input[type="' + axe.utils.escapeSelector(virtualNode.actualNode.type) + '"][name="' + name + '"]');
          if (matchingNodes.length < 2) {
            return true;
          }
          var fieldset = axe.commons.dom.findUpVirtual(virtualNode, 'fieldset');
          var group = axe.commons.dom.findUpVirtual(virtualNode, '[role="group"]' + (virtualNode.actualNode.type === 'radio' ? ',[role="radiogroup"]' : ''));
          if (!group && !fieldset) {
            failureCode = 'no-group';
            self.relatedNodes(spliceCurrentNode(matchingNodes, virtualNode.actualNode));
            return false;
          } else if (fieldset) {
            return checkFieldset(fieldset, name);
          } else {
            return checkARIAGroup(group, name);
          }
        }
        var data = {
          name: node.getAttribute('name'),
          type: node.getAttribute('type')
        };
        var result = runCheck(virtualNode);
        if (!result) {
          data.messageKey = failureCode;
        }
        this.data(data);
        return result;
      },
      after: function after(results, options) {
        var seen = {};
        return results.filter(function(result) {
          if (result.result) {
            return true;
          }
          var data = result.data;
          if (data) {
            seen[data.type] = seen[data.type] || {};
            if (!seen[data.type][data.name]) {
              seen[data.type][data.name] = [ data ];
              return true;
            }
            var hasBeenSeen = seen[data.type][data.name].some(function(candidate) {
              return candidate.failureCode === data.failureCode;
            });
            if (!hasBeenSeen) {
              seen[data.type][data.name].push(data);
            }
            return !hasBeenSeen;
          }
          return false;
        });
      },
      deprecated: true
    }, {
      id: 'group-labelledby',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons10 = axe.commons, dom = _axe$commons10.dom, text = _axe$commons10.text;
        var type = axe.utils.escapeSelector(node.type);
        var name = axe.utils.escapeSelector(node.name);
        var doc = dom.getRootNode(node);
        var data = {
          name: node.name,
          type: node.type
        };
        var matchingNodes = Array.from(doc.querySelectorAll('input[type="'.concat(type, '"][name="').concat(name, '"]')));
        if (matchingNodes.length <= 1) {
          this.data(data);
          return true;
        }
        var sharedLabels = dom.idrefs(node, 'aria-labelledby').filter(function(label) {
          return !!label;
        });
        var uniqueLabels = sharedLabels.slice();
        matchingNodes.forEach(function(groupItem) {
          if (groupItem === node) {
            return;
          }
          var labels = dom.idrefs(groupItem, 'aria-labelledby').filter(function(newLabel) {
            return newLabel;
          });
          sharedLabels = sharedLabels.filter(function(sharedLabel) {
            return labels.includes(sharedLabel);
          });
          uniqueLabels = uniqueLabels.filter(function(uniqueLabel) {
            return !labels.includes(uniqueLabel);
          });
        });
        var accessibleTextOptions = {
          inLabelledByContext: true
        };
        uniqueLabels = uniqueLabels.filter(function(labelNode) {
          return text.accessibleText(labelNode, accessibleTextOptions);
        });
        sharedLabels = sharedLabels.filter(function(labelNode) {
          return text.accessibleText(labelNode, accessibleTextOptions);
        });
        if (uniqueLabels.length > 0 && sharedLabels.length > 0) {
          this.data(data);
          return true;
        }
        if (uniqueLabels.length > 0 && sharedLabels.length === 0) {
          data.messageKey = 'no-shared-label';
        } else if (uniqueLabels.length === 0 && sharedLabels.length > 0) {
          data.messageKey = 'no-unique-label';
        }
        this.data(data);
        return false;
      },
      after: function after(results, options) {
        var seen = {};
        return results.filter(function(result) {
          var data = result.data;
          if (data) {
            seen[data.type] = seen[data.type] || {};
            if (!seen[data.type][data.name]) {
              seen[data.type][data.name] = true;
              return true;
            }
          }
          return false;
        });
      },
      deprecated: true
    }, {
      id: 'accesskeys',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (axe.commons.dom.isVisible(node, false)) {
          this.data(node.getAttribute('accesskey'));
          this.relatedNodes([ node ]);
        }
        return true;
      },
      after: function after(results, options) {
        var seen = {};
        return results.filter(function(r) {
          if (!r.data) {
            return false;
          }
          var key = r.data.toUpperCase();
          if (!seen[key]) {
            seen[key] = r;
            r.relatedNodes = [];
            return true;
          }
          seen[key].relatedNodes.push(r.relatedNodes[0]);
          return false;
        }).map(function(r) {
          r.result = !!r.relatedNodes.length;
          return r;
        });
      }
    }, {
      id: 'focusable-content',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var tabbableElements = virtualNode.tabbableElements;
        if (!tabbableElements) {
          return false;
        }
        var tabbableContentElements = tabbableElements.filter(function(el) {
          return el !== virtualNode;
        });
        return tabbableContentElements.length > 0;
      }
    }, {
      id: 'focusable-disabled',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var elementsThatCanBeDisabled = [ 'BUTTON', 'FIELDSET', 'INPUT', 'SELECT', 'TEXTAREA' ];
        var tabbableElements = virtualNode.tabbableElements;
        if (!tabbableElements || !tabbableElements.length) {
          return true;
        }
        var relatedNodes = tabbableElements.reduce(function(out, _ref3) {
          var el = _ref3.actualNode;
          var nodeName = el.nodeName.toUpperCase();
          if (elementsThatCanBeDisabled.includes(nodeName)) {
            out.push(el);
          }
          return out;
        }, []);
        this.relatedNodes(relatedNodes);
        if (relatedNodes.length && axe.commons.dom.isModalOpen()) {
          return true;
        }
        return relatedNodes.length === 0;
      }
    }, {
      id: 'focusable-element',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var isFocusable = virtualNode.isFocusable;
        var tabIndex = parseInt(virtualNode.actualNode.getAttribute('tabindex'), 10);
        tabIndex = !isNaN(tabIndex) ? tabIndex : null;
        return tabIndex ? isFocusable && tabIndex >= 0 : isFocusable;
      }
    }, {
      id: 'focusable-modal-open',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var tabbableElements = virtualNode.tabbableElements.map(function(_ref4) {
          var actualNode = _ref4.actualNode;
          return actualNode;
        });
        if (!tabbableElements || !tabbableElements.length) {
          return true;
        }
        if (axe.commons.dom.isModalOpen()) {
          this.relatedNodes(tabbableElements);
          return undefined;
        }
        return true;
      }
    }, {
      id: 'focusable-no-name',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var tabIndex = node.getAttribute('tabindex'), inFocusOrder = axe.commons.dom.isFocusable(node) && tabIndex > -1;
        if (!inFocusOrder) {
          return false;
        }
        return !axe.commons.text.accessibleTextVirtual(virtualNode);
      }
    }, {
      id: 'focusable-not-tabbable',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var elementsThatCanBeDisabled = [ 'BUTTON', 'FIELDSET', 'INPUT', 'SELECT', 'TEXTAREA' ];
        var tabbableElements = virtualNode.tabbableElements;
        if (!tabbableElements || !tabbableElements.length) {
          return true;
        }
        var relatedNodes = tabbableElements.reduce(function(out, _ref5) {
          var el = _ref5.actualNode;
          var nodeName = el.nodeName.toUpperCase();
          if (!elementsThatCanBeDisabled.includes(nodeName)) {
            out.push(el);
          }
          return out;
        }, []);
        this.relatedNodes(relatedNodes);
        if (relatedNodes.length > 0 && axe.commons.dom.isModalOpen()) {
          return true;
        }
        return relatedNodes.length === 0;
      }
    }, {
      id: 'landmark-is-top-level',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var landmarks = axe.commons.aria.getRolesByType('landmark');
        var parent = axe.commons.dom.getComposedParent(node);
        this.data({
          role: node.getAttribute('role') || axe.commons.aria.implicitRole(node)
        });
        while (parent) {
          var role = parent.getAttribute('role');
          if (!role && parent.nodeName.toUpperCase() !== 'FORM') {
            role = axe.commons.aria.implicitRole(parent);
          }
          if (role && landmarks.includes(role)) {
            return false;
          }
          parent = axe.commons.dom.getComposedParent(parent);
        }
        return true;
      }
    }, {
      id: 'page-has-heading-one',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (!options || !options.selector || typeof options.selector !== 'string') {
          throw new TypeError('visible-in-page requires options.selector to be a string');
        }
        var matchingElms = axe.utils.querySelectorAllFilter(virtualNode, options.selector, function(vNode) {
          return axe.commons.dom.isVisible(vNode.actualNode, true);
        });
        this.relatedNodes(matchingElms.map(function(vNode) {
          return vNode.actualNode;
        }));
        return matchingElms.length > 0;
      },
      after: function after(results, options) {
        var elmUsedAnywhere = results.some(function(frameResult) {
          return frameResult.result === true;
        });
        if (elmUsedAnywhere) {
          results.forEach(function(result) {
            result.result = true;
          });
        }
        return results;
      },
      options: {
        selector: 'h1:not([role]), [role="heading"][aria-level="1"]'
      }
    }, {
      id: 'page-has-main',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (!options || !options.selector || typeof options.selector !== 'string') {
          throw new TypeError('visible-in-page requires options.selector to be a string');
        }
        var matchingElms = axe.utils.querySelectorAllFilter(virtualNode, options.selector, function(vNode) {
          return axe.commons.dom.isVisible(vNode.actualNode, true);
        });
        this.relatedNodes(matchingElms.map(function(vNode) {
          return vNode.actualNode;
        }));
        return matchingElms.length > 0;
      },
      after: function after(results, options) {
        var elmUsedAnywhere = results.some(function(frameResult) {
          return frameResult.result === true;
        });
        if (elmUsedAnywhere) {
          results.forEach(function(result) {
            result.result = true;
          });
        }
        return results;
      },
      options: {
        selector: 'main:not([role]), [role=\'main\']'
      }
    }, {
      id: 'page-no-duplicate-banner',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (!options || !options.selector || typeof options.selector !== 'string') {
          throw new TypeError('visible-in-page requires options.selector to be a string');
        }
        var key = 'page-no-duplicate;' + options.selector;
        if (axe._cache.get(key)) {
          this.data('ignored');
          return;
        }
        axe._cache.set(key, true);
        var elms = axe.utils.querySelectorAllFilter(axe._tree[0], options.selector, function(elm) {
          return axe.commons.dom.isVisible(elm.actualNode);
        });
        if (typeof options.nativeScopeFilter === 'string') {
          elms = elms.filter(function(elm) {
            return elm.actualNode.hasAttribute('role') || !axe.commons.dom.findUpVirtual(elm, options.nativeScopeFilter);
          });
        }
        this.relatedNodes(elms.filter(function(elm) {
          return elm !== virtualNode;
        }).map(function(elm) {
          return elm.actualNode;
        }));
        return elms.length <= 1;
      },
      after: function after(results, options) {
        return results.filter(function(checkResult) {
          return checkResult.data !== 'ignored';
        });
      },
      options: {
        selector: 'header:not([role]), [role=banner]',
        nativeScopeFilter: 'article, aside, main, nav, section'
      }
    }, {
      id: 'page-no-duplicate-contentinfo',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (!options || !options.selector || typeof options.selector !== 'string') {
          throw new TypeError('visible-in-page requires options.selector to be a string');
        }
        var key = 'page-no-duplicate;' + options.selector;
        if (axe._cache.get(key)) {
          this.data('ignored');
          return;
        }
        axe._cache.set(key, true);
        var elms = axe.utils.querySelectorAllFilter(axe._tree[0], options.selector, function(elm) {
          return axe.commons.dom.isVisible(elm.actualNode);
        });
        if (typeof options.nativeScopeFilter === 'string') {
          elms = elms.filter(function(elm) {
            return elm.actualNode.hasAttribute('role') || !axe.commons.dom.findUpVirtual(elm, options.nativeScopeFilter);
          });
        }
        this.relatedNodes(elms.filter(function(elm) {
          return elm !== virtualNode;
        }).map(function(elm) {
          return elm.actualNode;
        }));
        return elms.length <= 1;
      },
      after: function after(results, options) {
        return results.filter(function(checkResult) {
          return checkResult.data !== 'ignored';
        });
      },
      options: {
        selector: 'footer:not([role]), [role=contentinfo]',
        nativeScopeFilter: 'article, aside, main, nav, section'
      }
    }, {
      id: 'page-no-duplicate-main',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (!options || !options.selector || typeof options.selector !== 'string') {
          throw new TypeError('visible-in-page requires options.selector to be a string');
        }
        var key = 'page-no-duplicate;' + options.selector;
        if (axe._cache.get(key)) {
          this.data('ignored');
          return;
        }
        axe._cache.set(key, true);
        var elms = axe.utils.querySelectorAllFilter(axe._tree[0], options.selector, function(elm) {
          return axe.commons.dom.isVisible(elm.actualNode);
        });
        if (typeof options.nativeScopeFilter === 'string') {
          elms = elms.filter(function(elm) {
            return elm.actualNode.hasAttribute('role') || !axe.commons.dom.findUpVirtual(elm, options.nativeScopeFilter);
          });
        }
        this.relatedNodes(elms.filter(function(elm) {
          return elm !== virtualNode;
        }).map(function(elm) {
          return elm.actualNode;
        }));
        return elms.length <= 1;
      },
      after: function after(results, options) {
        return results.filter(function(checkResult) {
          return checkResult.data !== 'ignored';
        });
      },
      options: {
        selector: 'main:not([role]), [role=\'main\']'
      }
    }, {
      id: 'tabindex',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var tabIndex = parseInt(node.getAttribute('tabindex'), 10);
        return isNaN(tabIndex) ? true : tabIndex <= 0;
      }
    }, {
      id: 'alt-space-value',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var alt = virtualNode.attr('alt');
        var isOnlySpace = /^\s+$/;
        return typeof alt === 'string' && isOnlySpace.test(alt);
      }
    }, {
      id: 'duplicate-img-label',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons11 = axe.commons, aria = _axe$commons11.aria, text = _axe$commons11.text, dom = _axe$commons11.dom;
        if ([ 'none', 'presentation' ].includes(aria.getRole(node))) {
          return false;
        }
        var parent = dom.findUpVirtual(virtualNode, 'button, [role="button"], a[href], p, li, td, th');
        if (!parent) {
          return false;
        }
        var parentVNode = axe.utils.getNodeFromTree(parent);
        var visibleText = text.visibleVirtual(parentVNode, true).toLowerCase();
        if (visibleText === '') {
          return false;
        }
        return visibleText === text.accessibleTextVirtual(virtualNode).toLowerCase();
      }
    }, {
      id: 'explicit-label',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (node.getAttribute('id')) {
          var root = axe.commons.dom.getRootNode(node);
          var id = axe.utils.escapeSelector(node.getAttribute('id'));
          var label = root.querySelector('label[for="'.concat(id, '"]'));
          if (label) {
            if (!axe.commons.dom.isVisible(label)) {
              return true;
            } else {
              return !!axe.commons.text.accessibleText(label);
            }
          }
        }
        return false;
      }
    }, {
      id: 'help-same-as-label',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var labelText = axe.commons.text.labelVirtual(virtualNode), check = node.getAttribute('title');
        if (!labelText) {
          return false;
        }
        if (!check) {
          check = '';
          if (node.getAttribute('aria-describedby')) {
            var ref = axe.commons.dom.idrefs(node, 'aria-describedby');
            check = ref.map(function(thing) {
              return thing ? axe.commons.text.accessibleText(thing) : '';
            }).join('');
          }
        }
        return axe.commons.text.sanitize(check) === axe.commons.text.sanitize(labelText);
      },
      enabled: false
    }, {
      id: 'hidden-explicit-label',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (node.getAttribute('id')) {
          var root = axe.commons.dom.getRootNode(node);
          var id = axe.utils.escapeSelector(node.getAttribute('id'));
          var label = root.querySelector('label[for="'.concat(id, '"]'));
          if (label && !axe.commons.dom.isVisible(label, true)) {
            var name = axe.commons.text.accessibleTextVirtual(virtualNode).trim();
            var isNameEmpty = name === '';
            return isNameEmpty;
          }
        }
        return false;
      }
    }, {
      id: 'implicit-label',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons12 = axe.commons, dom = _axe$commons12.dom, text = _axe$commons12.text;
        var label = dom.findUpVirtual(virtualNode, 'label');
        if (label) {
          return !!text.accessibleText(label, {
            inControlContext: true
          });
        }
        return false;
      }
    }, {
      id: 'label-content-name-mismatch',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var text = axe.commons.text;
        var _ref6 = options || {}, pixelThreshold = _ref6.pixelThreshold, occuranceThreshold = _ref6.occuranceThreshold;
        var accText = text.accessibleText(node).toLowerCase();
        if (text.isHumanInterpretable(accText) < 1) {
          return undefined;
        }
        var textVNodes = text.visibleTextNodes(virtualNode);
        var nonLigatureText = textVNodes.filter(function(textVNode) {
          return !text.isIconLigature(textVNode, pixelThreshold, occuranceThreshold);
        }).map(function(textVNode) {
          return textVNode.actualNode.nodeValue;
        }).join('');
        var visibleText = text.sanitize(nonLigatureText).toLowerCase();
        if (!visibleText) {
          return true;
        }
        if (text.isHumanInterpretable(visibleText) < 1) {
          if (isStringContained(visibleText, accText)) {
            return true;
          }
          return undefined;
        }
        return isStringContained(visibleText, accText);
        function isStringContained(compare, compareWith) {
          var curatedCompareWith = curateString(compareWith);
          var curatedCompare = curateString(compare);
          if (!curatedCompareWith || !curatedCompare) {
            return false;
          }
          return curatedCompareWith.includes(curatedCompare);
        }
        function curateString(str) {
          var noUnicodeStr = text.removeUnicode(str, {
            emoji: true,
            nonBmp: true,
            punctuations: true
          });
          return text.sanitize(noUnicodeStr);
        }
      },
      options: {
        pixelThreshold: .1,
        occuranceThreshold: 3
      }
    }, {
      id: 'multiple-label',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var id = axe.utils.escapeSelector(node.getAttribute('id'));
        var parent = node.parentNode;
        var root = axe.commons.dom.getRootNode(node);
        root = root.documentElement || root;
        var labels = Array.from(root.querySelectorAll('label[for="'.concat(id, '"]')));
        if (labels.length) {
          labels = labels.filter(function(label) {
            return axe.commons.dom.isVisible(label);
          });
        }
        while (parent) {
          if (parent.nodeName.toUpperCase() === 'LABEL' && labels.indexOf(parent) === -1) {
            labels.push(parent);
          }
          parent = parent.parentNode;
        }
        this.relatedNodes(labels);
        if (labels.length > 1) {
          var ATVisibleLabels = labels.filter(function(label) {
            return axe.commons.dom.isVisible(label, true);
          });
          if (ATVisibleLabels.length > 1) {
            return undefined;
          }
          var labelledby = axe.commons.dom.idrefs(node, 'aria-labelledby');
          return !labelledby.includes(ATVisibleLabels[0]) ? undefined : false;
        }
        return false;
      }
    }, {
      id: 'title-only',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var labelText = axe.commons.text.labelVirtual(virtualNode);
        return !labelText && !!(node.getAttribute('title') || node.getAttribute('aria-describedby'));
      }
    }, {
      id: 'landmark-is-unique',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var role = axe.commons.aria.getRole(node);
        var accessibleText = axe.commons.text.accessibleTextVirtual(virtualNode);
        accessibleText = accessibleText ? accessibleText.toLowerCase() : null;
        this.data({
          role: role,
          accessibleText: accessibleText
        });
        this.relatedNodes([ node ]);
        return true;
      },
      after: function after(results, options) {
        var uniqueLandmarks = [];
        return results.filter(function(currentResult) {
          var findMatch = function findMatch(someResult) {
            return currentResult.data.role === someResult.data.role && currentResult.data.accessibleText === someResult.data.accessibleText;
          };
          var matchedResult = uniqueLandmarks.find(findMatch);
          if (matchedResult) {
            matchedResult.result = false;
            matchedResult.relatedNodes.push(currentResult.relatedNodes[0]);
            return false;
          }
          uniqueLandmarks.push(currentResult);
          currentResult.relatedNodes = [];
          return true;
        });
      }
    }, {
      id: 'has-lang',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var isXHTML = axe.utils.isXHTML;
        var langValue = (node.getAttribute('lang') || '').trim();
        var xmlLangValue = (node.getAttribute('xml:lang') || '').trim();
        if (!langValue && xmlLangValue && !isXHTML(document)) {
          this.data({
            messageKey: 'noXHTML'
          });
          return false;
        }
        if (!(langValue || xmlLangValue)) {
          this.data({
            messageKey: 'noLang'
          });
          return false;
        }
        return true;
      }
    }, {
      id: 'valid-lang',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var langs, invalid;
        langs = (options ? options : axe.utils.validLangs()).map(axe.utils.getBaseLang);
        invalid = [ 'lang', 'xml:lang' ].reduce(function(invalid, langAttr) {
          var langVal = node.getAttribute(langAttr);
          if (typeof langVal !== 'string') {
            return invalid;
          }
          var baselangVal = axe.utils.getBaseLang(langVal);
          if (baselangVal !== '' && langs.indexOf(baselangVal) === -1) {
            invalid.push(langAttr + '="' + node.getAttribute(langAttr) + '"');
          }
          return invalid;
        }, []);
        if (invalid.length) {
          this.data(invalid);
          return true;
        }
        return false;
      }
    }, {
      id: 'xml-lang-mismatch',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var getBaseLang = axe.utils.getBaseLang;
        var primaryLangValue = getBaseLang(node.getAttribute('lang'));
        var primaryXmlLangValue = getBaseLang(node.getAttribute('xml:lang'));
        return primaryLangValue === primaryXmlLangValue;
      }
    }, {
      id: 'dlitem',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var parent = axe.commons.dom.getComposedParent(node);
        var parentTagName = parent.nodeName.toUpperCase();
        var parentRole = axe.commons.aria.getRole(parent, {
          noImplicit: true
        });
        if (parentTagName === 'DIV' && [ 'presentation', 'none', null ].includes(parentRole)) {
          parent = axe.commons.dom.getComposedParent(parent);
          parentTagName = parent.nodeName.toUpperCase();
          parentRole = axe.commons.aria.getRole(parent, {
            noImplicit: true
          });
        }
        if (parentTagName !== 'DL') {
          return false;
        }
        if (!parentRole || parentRole === 'list') {
          return true;
        }
        return false;
      }
    }, {
      id: 'listitem',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var parent = axe.commons.dom.getComposedParent(node);
        if (!parent) {
          return undefined;
        }
        var parentTagName = parent.nodeName.toUpperCase();
        var parentRole = (parent.getAttribute('role') || '').toLowerCase();
        if ([ 'presentation', 'none', 'list' ].includes(parentRole)) {
          return true;
        }
        if (parentRole && axe.commons.aria.isValidRole(parentRole)) {
          this.data({
            messageKey: 'roleNotValid'
          });
          return false;
        }
        return [ 'UL', 'OL' ].includes(parentTagName);
      }
    }, {
      id: 'only-dlitems',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons13 = axe.commons, dom = _axe$commons13.dom, aria = _axe$commons13.aria;
        var ALLOWED_ROLES = [ 'definition', 'term', 'list' ];
        var base = {
          badNodes: [],
          hasNonEmptyTextNode: false
        };
        var content = virtualNode.children.reduce(function(content, child) {
          var actualNode = child.actualNode;
          if (actualNode.nodeName.toUpperCase() === 'DIV' && aria.getRole(actualNode) === null) {
            return content.concat(child.children);
          }
          return content.concat(child);
        }, []);
        var result = content.reduce(function(out, childNode) {
          var actualNode = childNode.actualNode;
          var tagName = actualNode.nodeName.toUpperCase();
          if (actualNode.nodeType === 1 && dom.isVisible(actualNode, true, false)) {
            var explicitRole = aria.getRole(actualNode, {
              noImplicit: true
            });
            if (tagName !== 'DT' && tagName !== 'DD' || explicitRole) {
              if (!ALLOWED_ROLES.includes(explicitRole)) {
                out.badNodes.push(actualNode);
              }
            }
          } else if (actualNode.nodeType === 3 && actualNode.nodeValue.trim() !== '') {
            out.hasNonEmptyTextNode = true;
          }
          return out;
        }, base);
        if (result.badNodes.length) {
          this.relatedNodes(result.badNodes);
        }
        return !!result.badNodes.length || result.hasNonEmptyTextNode;
      }
    }, {
      id: 'only-listitems',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons14 = axe.commons, dom = _axe$commons14.dom, aria = _axe$commons14.aria;
        var hasNonEmptyTextNode = false;
        var atLeastOneListitem = false;
        var isEmpty = true;
        var badNodes = [];
        var badRoleNodes = [];
        var badRoles = [];
        virtualNode.children.forEach(function(vNode) {
          var actualNode = vNode.actualNode;
          if (actualNode.nodeType === 3 && actualNode.nodeValue.trim() !== '') {
            hasNonEmptyTextNode = true;
            return;
          }
          if (actualNode.nodeType !== 1 || !dom.isVisible(actualNode, true, false)) {
            return;
          }
          isEmpty = false;
          var isLi = actualNode.nodeName.toUpperCase() === 'LI';
          var role = aria.getRole(vNode);
          var isListItemRole = role === 'listitem';
          if (!isLi && !isListItemRole) {
            badNodes.push(actualNode);
          }
          if (isLi && !isListItemRole) {
            badRoleNodes.push(actualNode);
            if (!badRoles.includes(role)) {
              badRoles.push(role);
            }
          }
          if (isListItemRole) {
            atLeastOneListitem = true;
          }
        });
        if (hasNonEmptyTextNode || badNodes.length) {
          this.relatedNodes(badNodes);
          return true;
        }
        if (isEmpty || atLeastOneListitem) {
          return false;
        }
        this.relatedNodes(badRoleNodes);
        this.data({
          messageKey: 'roleNotValid',
          roles: badRoles.join(', ')
        });
        return true;
      }
    }, {
      id: 'structured-dlitems',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var children = virtualNode.children;
        if (!children || !children.length) {
          return false;
        }
        var hasDt = false, hasDd = false, nodeName;
        for (var i = 0; i < children.length; i++) {
          nodeName = children[i].actualNode.nodeName.toUpperCase();
          if (nodeName === 'DT') {
            hasDt = true;
          }
          if (hasDt && nodeName === 'DD') {
            return false;
          }
          if (nodeName === 'DD') {
            hasDd = true;
          }
        }
        return hasDt || hasDd;
      }
    }, {
      id: 'caption',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var tracks = axe.utils.querySelectorAll(virtualNode, 'track');
        var hasCaptions = tracks.some(function(_ref7) {
          var actualNode = _ref7.actualNode;
          return (actualNode.getAttribute('kind') || '').toLowerCase() === 'captions';
        });
        return hasCaptions ? false : undefined;
      }
    }, {
      id: 'description',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var tracks = axe.utils.querySelectorAll(virtualNode, 'track');
        var hasDescriptions = tracks.some(function(_ref8) {
          var actualNode = _ref8.actualNode;
          return (actualNode.getAttribute('kind') || '').toLowerCase() === 'descriptions';
        });
        return hasDescriptions ? false : undefined;
      }
    }, {
      id: 'frame-tested',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var resolve = this.async();
        var _Object$assign = Object.assign({
          isViolation: false,
          timeout: 500
        }, options), isViolation = _Object$assign.isViolation, timeout = _Object$assign.timeout;
        var timer = setTimeout(function() {
          timer = setTimeout(function() {
            timer = null;
            resolve(isViolation ? false : undefined);
          }, 0);
        }, timeout);
        axe.utils.respondable(node.contentWindow, 'axe.ping', null, undefined, function() {
          if (timer !== null) {
            clearTimeout(timer);
            resolve(true);
          }
        });
      },
      options: {
        isViolation: false
      }
    }, {
      id: 'no-autoplay-audio',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (!node.duration) {
          console.warn('axe.utils.preloadMedia did not load metadata');
          return undefined;
        }
        var _options$allowedDurat = options.allowedDuration, allowedDuration = _options$allowedDurat === void 0 ? 3 : _options$allowedDurat;
        var playableDuration = getPlayableDuration(node);
        if (playableDuration <= allowedDuration && !node.hasAttribute('loop')) {
          return true;
        }
        if (!node.hasAttribute('controls')) {
          return false;
        }
        return true;
        function getPlayableDuration(elm) {
          if (!elm.currentSrc) {
            return 0;
          }
          var playbackRange = getPlaybackRange(elm.currentSrc);
          if (!playbackRange) {
            return Math.abs(elm.duration - (elm.currentTime || 0));
          }
          if (playbackRange.length === 1) {
            return Math.abs(elm.duration - playbackRange[0]);
          }
          return Math.abs(playbackRange[1] - playbackRange[0]);
        }
        function getPlaybackRange(src) {
          var match = src.match(/#t=(.*)/);
          if (!match) {
            return;
          }
          var _match = _slicedToArray(match, 2), value = _match[1];
          var ranges = value.split(',');
          return ranges.map(function(range) {
            if (/:/.test(range)) {
              return convertHourMinSecToSeconds(range);
            }
            return parseFloat(range);
          });
        }
        function convertHourMinSecToSeconds(hhMmSs) {
          var parts = hhMmSs.split(':');
          var secs = 0;
          var mins = 1;
          while (parts.length > 0) {
            secs += mins * parseInt(parts.pop(), 10);
            mins *= 60;
          }
          return parseFloat(secs);
        }
      },
      options: {
        allowedDuration: 3
      }
    }, {
      id: 'css-orientation-lock',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _ref9 = context || {}, _ref9$cssom = _ref9.cssom, cssom = _ref9$cssom === void 0 ? undefined : _ref9$cssom;
        var _ref10 = options || {}, _ref10$degreeThreshol = _ref10.degreeThreshold, degreeThreshold = _ref10$degreeThreshol === void 0 ? 0 : _ref10$degreeThreshol;
        if (!cssom || !cssom.length) {
          return undefined;
        }
        var isLocked = false;
        var relatedElements = [];
        var rulesGroupByDocumentFragment = groupCssomByDocument(cssom);
        var _loop = function _loop() {
          var key = _Object$keys[_i2];
          var _rulesGroupByDocument = rulesGroupByDocumentFragment[key], root = _rulesGroupByDocument.root, rules = _rulesGroupByDocument.rules;
          var orientationRules = rules.filter(isMediaRuleWithOrientation);
          if (!orientationRules.length) {
            return 'continue';
          }
          orientationRules.forEach(function(_ref16) {
            var cssRules = _ref16.cssRules;
            Array.from(cssRules).forEach(function(cssRule) {
              var locked = getIsOrientationLocked(cssRule);
              if (locked && cssRule.selectorText.toUpperCase() !== 'HTML') {
                var elms = Array.from(root.querySelectorAll(cssRule.selectorText)) || [];
                relatedElements = relatedElements.concat(elms);
              }
              isLocked = isLocked || locked;
            });
          });
        };
        for (var _i2 = 0, _Object$keys = Object.keys(rulesGroupByDocumentFragment); _i2 < _Object$keys.length; _i2++) {
          var _ret = _loop();
          if (_ret === 'continue') {
            continue;
          }
        }
        if (!isLocked) {
          return true;
        }
        if (relatedElements.length) {
          this.relatedNodes(relatedElements);
        }
        return false;
        function groupCssomByDocument(cssObjectModel) {
          return cssObjectModel.reduce(function(out, _ref11) {
            var sheet = _ref11.sheet, root = _ref11.root, shadowId = _ref11.shadowId;
            var key = shadowId ? shadowId : 'topDocument';
            if (!out[key]) {
              out[key] = {
                root: root,
                rules: []
              };
            }
            if (!sheet || !sheet.cssRules) {
              return out;
            }
            var rules = Array.from(sheet.cssRules);
            out[key].rules = out[key].rules.concat(rules);
            return out;
          }, {});
        }
        function isMediaRuleWithOrientation(_ref12) {
          var type = _ref12.type, cssText = _ref12.cssText;
          if (type !== 4) {
            return false;
          }
          return /orientation:\s*landscape/i.test(cssText) || /orientation:\s*portrait/i.test(cssText);
        }
        function getIsOrientationLocked(_ref13) {
          var selectorText = _ref13.selectorText, style = _ref13.style;
          if (!selectorText || style.length <= 0) {
            return false;
          }
          var transformStyle = style.transform || style.webkitTransform || style.msTransform || false;
          if (!transformStyle) {
            return false;
          }
          var matches = transformStyle.match(/(rotate|rotateZ|rotate3d|matrix|matrix3d)\(([^)]+)\)(?!.*(rotate|rotateZ|rotate3d|matrix|matrix3d))/);
          if (!matches) {
            return false;
          }
          var _matches = _slicedToArray(matches, 3), transformFn = _matches[1], transformFnValue = _matches[2];
          var degrees = getRotationInDegrees(transformFn, transformFnValue);
          if (!degrees) {
            return false;
          }
          degrees = Math.abs(degrees);
          if (Math.abs(degrees - 180) % 180 <= degreeThreshold) {
            return false;
          }
          return Math.abs(degrees - 90) % 90 <= degreeThreshold;
        }
        function getRotationInDegrees(transformFunction, transformFnValue) {
          switch (transformFunction) {
           case 'rotate':
           case 'rotateZ':
            return getAngleInDegrees(transformFnValue);

           case 'rotate3d':
            var _transformFnValue$spl = transformFnValue.split(',').map(function(value) {
              return value.trim();
            }), _transformFnValue$spl2 = _slicedToArray(_transformFnValue$spl, 4), z = _transformFnValue$spl2[2], angleWithUnit = _transformFnValue$spl2[3];
            if (parseInt(z) === 0) {
              return;
            }
            return getAngleInDegrees(angleWithUnit);

           case 'matrix':
           case 'matrix3d':
            return getAngleInDegreesFromMatrixTransform(transformFnValue);

           default:
            return;
          }
        }
        function getAngleInDegrees(angleWithUnit) {
          var _ref14 = angleWithUnit.match(/(deg|grad|rad|turn)/) || [], _ref15 = _slicedToArray(_ref14, 1), unit = _ref15[0];
          if (!unit) {
            return;
          }
          var angle = parseFloat(angleWithUnit.replace(unit, ''));
          switch (unit) {
           case 'rad':
            return convertRadToDeg(angle);

           case 'grad':
            return convertGradToDeg(angle);

           case 'turn':
            return convertTurnToDeg(angle);

           case 'deg':
           default:
            return parseInt(angle);
          }
        }
        function getAngleInDegreesFromMatrixTransform(transformFnValue) {
          var values = transformFnValue.split(',');
          if (values.length <= 6) {
            var _values = _slicedToArray(values, 2), a = _values[0], _b = _values[1];
            var radians = Math.atan2(parseFloat(_b), parseFloat(a));
            return convertRadToDeg(radians);
          }
          var sinB = parseFloat(values[8]);
          var b = Math.asin(sinB);
          var cosB = Math.cos(b);
          var rotateZRadians = Math.acos(parseFloat(values[0]) / cosB);
          return convertRadToDeg(rotateZRadians);
        }
        function convertRadToDeg(radians) {
          return Math.round(radians * (180 / Math.PI));
        }
        function convertGradToDeg(grad) {
          grad = grad % 400;
          if (grad < 0) {
            grad += 400;
          }
          return Math.round(grad / 400 * 360);
        }
        function convertTurnToDeg(turn) {
          return Math.round(360 / (1 / turn));
        }
      },
      options: {
        degreeThreshold: 2
      }
    }, {
      id: 'meta-viewport-large',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _ref17 = options || {}, _ref17$scaleMinimum = _ref17.scaleMinimum, scaleMinimum = _ref17$scaleMinimum === void 0 ? 2 : _ref17$scaleMinimum, _ref17$lowerBound = _ref17.lowerBound, lowerBound = _ref17$lowerBound === void 0 ? false : _ref17$lowerBound;
        var content = node.getAttribute('content') || '';
        if (!content) {
          return true;
        }
        var result = content.split(/[;,]/).reduce(function(out, item) {
          var contentValue = item.trim();
          if (!contentValue) {
            return out;
          }
          var _contentValue$split = contentValue.split('='), _contentValue$split2 = _slicedToArray(_contentValue$split, 2), key = _contentValue$split2[0], value = _contentValue$split2[1];
          if (!key || !value) {
            return out;
          }
          var curatedKey = key.toLowerCase().trim();
          var curatedValue = value.toLowerCase().trim();
          if (curatedKey === 'maximum-scale' && curatedValue === 'yes') {
            curatedValue = 1;
          }
          if (curatedKey === 'maximum-scale' && parseFloat(curatedValue) < 0) {
            return out;
          }
          out[curatedKey] = curatedValue;
          return out;
        }, {});
        if (lowerBound && result['maximum-scale'] && parseFloat(result['maximum-scale']) < lowerBound) {
          return true;
        }
        if (!lowerBound && result['user-scalable'] === 'no') {
          this.data('user-scalable=no');
          return false;
        }
        if (result['maximum-scale'] && parseFloat(result['maximum-scale']) < scaleMinimum) {
          this.data('maximum-scale');
          return false;
        }
        return true;
      },
      options: {
        scaleMinimum: 5,
        lowerBound: 2
      }
    }, {
      id: 'meta-viewport',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _ref18 = options || {}, _ref18$scaleMinimum = _ref18.scaleMinimum, scaleMinimum = _ref18$scaleMinimum === void 0 ? 2 : _ref18$scaleMinimum, _ref18$lowerBound = _ref18.lowerBound, lowerBound = _ref18$lowerBound === void 0 ? false : _ref18$lowerBound;
        var content = node.getAttribute('content') || '';
        if (!content) {
          return true;
        }
        var result = content.split(/[;,]/).reduce(function(out, item) {
          var contentValue = item.trim();
          if (!contentValue) {
            return out;
          }
          var _contentValue$split3 = contentValue.split('='), _contentValue$split4 = _slicedToArray(_contentValue$split3, 2), key = _contentValue$split4[0], value = _contentValue$split4[1];
          if (!key || !value) {
            return out;
          }
          var curatedKey = key.toLowerCase().trim();
          var curatedValue = value.toLowerCase().trim();
          if (curatedKey === 'maximum-scale' && curatedValue === 'yes') {
            curatedValue = 1;
          }
          if (curatedKey === 'maximum-scale' && parseFloat(curatedValue) < 0) {
            return out;
          }
          out[curatedKey] = curatedValue;
          return out;
        }, {});
        if (lowerBound && result['maximum-scale'] && parseFloat(result['maximum-scale']) < lowerBound) {
          return true;
        }
        if (!lowerBound && result['user-scalable'] === 'no') {
          this.data('user-scalable=no');
          return false;
        }
        if (result['maximum-scale'] && parseFloat(result['maximum-scale']) < scaleMinimum) {
          this.data('maximum-scale');
          return false;
        }
        return true;
      },
      options: {
        scaleMinimum: 2
      }
    }, {
      id: 'header-present',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return !!axe.utils.querySelectorAll(virtualNode, 'h1, h2, h3, h4, h5, h6, [role="heading"]')[0];
      }
    }, {
      id: 'heading-order',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var ariaHeadingLevel = node.getAttribute('aria-level');
        if (ariaHeadingLevel !== null) {
          this.data(parseInt(ariaHeadingLevel, 10));
          return true;
        }
        var headingLevel = node.nodeName.toUpperCase().match(/H(\d)/);
        if (headingLevel) {
          this.data(parseInt(headingLevel[1], 10));
          return true;
        }
        return true;
      },
      after: function after(results, options) {
        if (results.length < 2) {
          return results;
        }
        var prevLevel = results[0].data;
        for (var i = 1; i < results.length; i++) {
          if (results[i].result && results[i].data > prevLevel + 1) {
            results[i].result = false;
          }
          prevLevel = results[i].data;
        }
        return results;
      }
    }, {
      id: 'identical-links-same-purpose',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons15 = axe.commons, dom = _axe$commons15.dom, text = _axe$commons15.text;
        var accText = text.accessibleTextVirtual(virtualNode);
        var name = text.sanitize(text.removeUnicode(accText, {
          emoji: true,
          nonBmp: true,
          punctuations: true
        })).toLowerCase();
        if (!name) {
          return undefined;
        }
        var afterData = {
          name: name,
          urlProps: dom.urlPropsFromAttribute(node, 'href')
        };
        this.data(afterData);
        this.relatedNodes([ node ]);
        return true;
      },
      after: function after(results, options) {
        if (results.length < 2) {
          return results;
        }
        var incompleteResults = results.filter(function(_ref19) {
          var result = _ref19.result;
          return result !== undefined;
        });
        var uniqueResults = [];
        var nameMap = {};
        var _loop2 = function _loop2(index) {
          var _currentResult$relate;
          var currentResult = incompleteResults[index];
          var _currentResult$data = currentResult.data, name = _currentResult$data.name, urlProps = _currentResult$data.urlProps;
          if (nameMap[name]) {
            return 'continue';
          }
          var sameNameResults = incompleteResults.filter(function(_ref20, resultNum) {
            var data = _ref20.data;
            return data.name === name && resultNum !== index;
          });
          var isSameUrl = sameNameResults.every(function(_ref21) {
            var data = _ref21.data;
            return isIdenticalObject(data.urlProps, urlProps);
          });
          if (sameNameResults.length && !isSameUrl) {
            currentResult.result = undefined;
          }
          currentResult.relatedNodes = [];
          (_currentResult$relate = currentResult.relatedNodes).push.apply(_currentResult$relate, _toConsumableArray(sameNameResults.map(function(node) {
            return node.relatedNodes[0];
          })));
          nameMap[name] = sameNameResults;
          uniqueResults.push(currentResult);
        };
        for (var index = 0; index < incompleteResults.length; index++) {
          var _ret2 = _loop2(index);
          if (_ret2 === 'continue') {
            continue;
          }
        }
        return uniqueResults;
        function isIdenticalObject(a, b) {
          if (!a || !b) {
            return false;
          }
          var aProps = Object.getOwnPropertyNames(a);
          var bProps = Object.getOwnPropertyNames(b);
          if (aProps.length !== bProps.length) {
            return false;
          }
          var result = aProps.every(function(propName) {
            var aValue = a[propName];
            var bValue = b[propName];
            if (_typeof(aValue) !== _typeof(bValue)) {
              return false;
            }
            if (typeof aValue === 'object' || typeof bValue === 'object') {
              return isIdenticalObject(aValue, bValue);
            }
            return aValue === bValue;
          });
          return result;
        }
      }
    }, {
      id: 'internal-link-present',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var links = axe.utils.querySelectorAll(virtualNode, 'a[href]');
        return links.some(function(vLink) {
          return /^#[^/!]/.test(vLink.actualNode.getAttribute('href'));
        });
      }
    }, {
      id: 'landmark',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return axe.utils.querySelectorAll(virtualNode, 'main, [role="main"]').length > 0;
      }
    }, {
      id: 'meta-refresh',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var content = node.getAttribute('content') || '', parsedParams = content.split(/[;,]/);
        return content === '' || parsedParams[0] === '0';
      }
    }, {
      id: 'p-as-heading',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var siblings = Array.from(node.parentNode.children);
        var currentIndex = siblings.indexOf(node);
        options = options || {};
        var margins = options.margins || [];
        var nextSibling = siblings.slice(currentIndex + 1).find(function(elm) {
          return elm.nodeName.toUpperCase() === 'P';
        });
        var prevSibling = siblings.slice(0, currentIndex).reverse().find(function(elm) {
          return elm.nodeName.toUpperCase() === 'P';
        });
        function getTextContainer(elm) {
          var nextNode = elm;
          var outerText = elm.textContent.trim();
          var innerText = outerText;
          while (innerText === outerText && nextNode !== undefined) {
            var i = -1;
            elm = nextNode;
            if (elm.children.length === 0) {
              return elm;
            }
            do {
              i++;
              innerText = elm.children[i].textContent.trim();
            } while (innerText === '' && i + 1 < elm.children.length);
            nextNode = elm.children[i];
          }
          return elm;
        }
        function normalizeFontWeight(weight) {
          switch (weight) {
           case 'lighter':
            return 100;

           case 'normal':
            return 400;

           case 'bold':
            return 700;

           case 'bolder':
            return 900;
          }
          weight = parseInt(weight);
          return !isNaN(weight) ? weight : 400;
        }
        function getStyleValues(node) {
          var style = window.getComputedStyle(getTextContainer(node));
          return {
            fontWeight: normalizeFontWeight(style.getPropertyValue('font-weight')),
            fontSize: parseInt(style.getPropertyValue('font-size')),
            isItalic: style.getPropertyValue('font-style') === 'italic'
          };
        }
        function isHeaderStyle(styleA, styleB, margins) {
          return margins.reduce(function(out, margin) {
            return out || (!margin.size || styleA.fontSize / margin.size > styleB.fontSize) && (!margin.weight || styleA.fontWeight - margin.weight > styleB.fontWeight) && (!margin.italic || styleA.isItalic && !styleB.isItalic);
          }, false);
        }
        var currStyle = getStyleValues(node);
        var nextStyle = nextSibling ? getStyleValues(nextSibling) : null;
        var prevStyle = prevSibling ? getStyleValues(prevSibling) : null;
        if (!nextStyle || !isHeaderStyle(currStyle, nextStyle, margins)) {
          return true;
        }
        var blockquote = axe.commons.dom.findUpVirtual(virtualNode, 'blockquote');
        if (blockquote && blockquote.nodeName.toUpperCase() === 'BLOCKQUOTE') {
          return undefined;
        }
        if (prevStyle && !isHeaderStyle(currStyle, prevStyle, margins)) {
          return undefined;
        }
        return false;
      },
      options: {
        margins: [ {
          weight: 150,
          italic: true
        }, {
          weight: 150,
          size: 1.15
        }, {
          italic: true,
          size: 1.15
        }, {
          size: 1.4
        } ]
      }
    }, {
      id: 'region',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons16 = axe.commons, dom = _axe$commons16.dom, aria = _axe$commons16.aria;
        var landmarkRoles = aria.getRolesByType('landmark');
        var implicitAriaLiveRoles = [ 'alert', 'log', 'status' ];
        var regionlessNodes = axe._cache.get('regionlessNodes');
        if (regionlessNodes) {
          return !regionlessNodes.includes(virtualNode);
        }
        var implicitLandmarks = landmarkRoles.reduce(function(arr, role) {
          return arr.concat(aria.implicitNodes(role));
        }, []).filter(function(r) {
          return r !== null;
        });
        function isRegion(virtualNode) {
          var node = virtualNode.actualNode;
          var explicitRole = axe.commons.aria.getRole(node, {
            noImplicit: true
          });
          var ariaLive = (node.getAttribute('aria-live') || '').toLowerCase().trim();
          if ([ 'assertive', 'polite' ].includes(ariaLive) || implicitAriaLiveRoles.includes(explicitRole)) {
            return true;
          }
          if (explicitRole) {
            return explicitRole === 'dialog' || landmarkRoles.includes(explicitRole);
          }
          return implicitLandmarks.some(function(implicitSelector) {
            var matches = axe.utils.matchesSelector(node, implicitSelector);
            if (node.nodeName.toUpperCase() === 'FORM') {
              var titleAttr = node.getAttribute('title');
              var title = titleAttr && titleAttr.trim() !== '' ? axe.commons.text.sanitize(titleAttr) : null;
              return matches && (!!aria.labelVirtual(virtualNode) || !!title);
            }
            return matches;
          });
        }
        function findRegionlessElms(virtualNode) {
          var node = virtualNode.actualNode;
          if (isRegion(virtualNode) || dom.isSkipLink(virtualNode.actualNode) && dom.getElementByReference(virtualNode.actualNode, 'href') || !dom.isVisible(node, true)) {
            var vNode = virtualNode;
            while (vNode) {
              vNode._hasRegionDescendant = true;
              vNode = vNode.parent;
            }
            return [];
          } else if (node !== document.body && dom.hasContent(node, true)) {
            return [ virtualNode ];
          } else {
            return virtualNode.children.filter(function(_ref22) {
              var actualNode = _ref22.actualNode;
              return actualNode.nodeType === 1;
            }).map(findRegionlessElms).reduce(function(a, b) {
              return a.concat(b);
            }, []);
          }
        }
        regionlessNodes = findRegionlessElms(axe._tree[0]).map(function(vNode) {
          while (vNode.parent && !vNode.parent._hasRegionDescendant && vNode.parent.actualNode !== document.body) {
            vNode = vNode.parent;
          }
          return vNode;
        }).filter(function(vNode, index, array) {
          return array.indexOf(vNode) === index;
        });
        axe._cache.set('regionlessNodes', regionlessNodes);
        return !regionlessNodes.includes(virtualNode);
      }
    }, {
      id: 'skip-link',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var target = axe.commons.dom.getElementByReference(node, 'href');
        if (target) {
          return axe.commons.dom.isVisible(target, true) || undefined;
        }
        return false;
      }
    }, {
      id: 'unique-frame-title',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var title = axe.commons.text.sanitize(node.title).trim().toLowerCase();
        this.data(title);
        return true;
      },
      after: function after(results, options) {
        var titles = {};
        results.forEach(function(r) {
          titles[r.data] = titles[r.data] !== undefined ? ++titles[r.data] : 0;
        });
        results.forEach(function(r) {
          r.result = !!titles[r.data];
        });
        return results;
      }
    }, {
      id: 'duplicate-id-active',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var id = node.getAttribute('id').trim();
        if (!id) {
          return true;
        }
        var root = axe.commons.dom.getRootNode(node);
        var matchingNodes = Array.from(root.querySelectorAll('[id="'.concat(axe.utils.escapeSelector(id), '"]'))).filter(function(foundNode) {
          return foundNode !== node;
        });
        if (matchingNodes.length) {
          this.relatedNodes(matchingNodes);
        }
        this.data(id);
        return matchingNodes.length === 0;
      },
      after: function after(results, options) {
        var uniqueIds = [];
        return results.filter(function(r) {
          if (uniqueIds.indexOf(r.data) === -1) {
            uniqueIds.push(r.data);
            return true;
          }
          return false;
        });
      }
    }, {
      id: 'duplicate-id-aria',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var id = node.getAttribute('id').trim();
        if (!id) {
          return true;
        }
        var root = axe.commons.dom.getRootNode(node);
        var matchingNodes = Array.from(root.querySelectorAll('[id="'.concat(axe.utils.escapeSelector(id), '"]'))).filter(function(foundNode) {
          return foundNode !== node;
        });
        if (matchingNodes.length) {
          this.relatedNodes(matchingNodes);
        }
        this.data(id);
        return matchingNodes.length === 0;
      },
      after: function after(results, options) {
        var uniqueIds = [];
        return results.filter(function(r) {
          if (uniqueIds.indexOf(r.data) === -1) {
            uniqueIds.push(r.data);
            return true;
          }
          return false;
        });
      }
    }, {
      id: 'duplicate-id',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var id = node.getAttribute('id').trim();
        if (!id) {
          return true;
        }
        var root = axe.commons.dom.getRootNode(node);
        var matchingNodes = Array.from(root.querySelectorAll('[id="'.concat(axe.utils.escapeSelector(id), '"]'))).filter(function(foundNode) {
          return foundNode !== node;
        });
        if (matchingNodes.length) {
          this.relatedNodes(matchingNodes);
        }
        this.data(id);
        return matchingNodes.length === 0;
      },
      after: function after(results, options) {
        var uniqueIds = [];
        return results.filter(function(r) {
          if (uniqueIds.indexOf(r.data) === -1) {
            uniqueIds.push(r.data);
            return true;
          }
          return false;
        });
      }
    }, {
      id: 'aria-label',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons17 = axe.commons, text = _axe$commons17.text, aria = _axe$commons17.aria;
        return !!text.sanitize(aria.arialabelText(virtualNode));
      }
    }, {
      id: 'aria-labelledby',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var _axe$commons18 = axe.commons, text = _axe$commons18.text, aria = _axe$commons18.aria;
        return !!text.sanitize(aria.arialabelledbyText(node));
      }
    }, {
      id: 'avoid-inline-spacing',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var inlineSpacingCssProperties = [ 'line-height', 'letter-spacing', 'word-spacing' ];
        var overriddenProperties = inlineSpacingCssProperties.filter(function(property) {
          if (node.style.getPropertyPriority(property) === 'important') {
            return property;
          }
        });
        if (overriddenProperties.length > 0) {
          this.data(overriddenProperties);
          return false;
        }
        return true;
      }
    }, {
      id: 'button-has-visible-text',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var nodeName = node.nodeName.toUpperCase();
        var role = node.getAttribute('role');
        var label;
        if (nodeName === 'BUTTON' || role === 'button' && nodeName !== 'INPUT') {
          label = axe.commons.text.accessibleTextVirtual(virtualNode);
          this.data(label);
          return !!label;
        } else {
          return false;
        }
      }
    }, {
      id: 'doc-has-title',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var title = document.title;
        return !!(title ? axe.commons.text.sanitize(title).trim() : '');
      }
    }, {
      id: 'exists',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return undefined;
      }
    }, {
      id: 'has-alt',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var nodeName = virtualNode.props.nodeName;
        if (![ 'img', 'input', 'area' ].includes(nodeName)) {
          return false;
        }
        return virtualNode.hasAttr('alt');
      }
    }, {
      id: 'has-visible-text',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return axe.commons.text.accessibleTextVirtual(virtualNode).length > 0;
      }
    }, {
      id: 'is-on-screen',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return axe.commons.dom.isVisible(node, false) && !axe.commons.dom.isOffscreen(node);
      }
    }, {
      id: 'non-empty-alt',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var label = virtualNode.attr('alt');
        return !!(label ? axe.commons.text.sanitize(label).trim() : '');
      }
    }, {
      id: 'non-empty-if-present',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var nodeName = node.nodeName.toUpperCase();
        var type = (node.getAttribute('type') || '').toLowerCase();
        var label = node.getAttribute('value');
        if (label) {
          this.data({
            messageKey: 'has-label'
          });
        }
        if (nodeName === 'INPUT' && [ 'submit', 'reset' ].includes(type)) {
          return label === null;
        }
        return false;
      }
    }, {
      id: 'non-empty-title',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var text = axe.commons.text;
        return !!text.sanitize(text.titleText(node));
      }
    }, {
      id: 'non-empty-value',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var label = node.getAttribute('value');
        return !!(label ? axe.commons.text.sanitize(label).trim() : '');
      }
    }, {
      id: 'role-none',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return node.getAttribute('role') === 'none';
      }
    }, {
      id: 'role-presentation',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return node.getAttribute('role') === 'presentation';
      }
    }, {
      id: 'svg-non-empty-title',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var titleNode = virtualNode.children.find(function(_ref23) {
          var props = _ref23.props;
          return props.nodeName === 'title';
        });
        return !!titleNode && titleNode.actualNode.textContent.trim() !== '';
      }
    }, {
      id: 'caption-faked',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var table = axe.commons.table.toGrid(node);
        var firstRow = table[0];
        if (table.length <= 1 || firstRow.length <= 1 || node.rows.length <= 1) {
          return true;
        }
        return firstRow.reduce(function(out, curr, i) {
          return out || curr !== firstRow[i + 1] && firstRow[i + 1] !== undefined;
        }, false);
      }
    }, {
      id: 'has-caption',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return !!node.caption;
      },
      deprecated: true
    }, {
      id: 'has-summary',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return !!node.summary;
      },
      deprecated: true
    }, {
      id: 'has-th',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var row, cell, badCells = [];
        for (var rowIndex = 0, rowLength = node.rows.length; rowIndex < rowLength; rowIndex++) {
          row = node.rows[rowIndex];
          for (var cellIndex = 0, cellLength = row.cells.length; cellIndex < cellLength; cellIndex++) {
            cell = row.cells[cellIndex];
            if (cell.nodeName.toUpperCase() === 'TH' || [ 'rowheader', 'columnheader' ].indexOf(cell.getAttribute('role')) !== -1) {
              badCells.push(cell);
            }
          }
        }
        if (badCells.length) {
          this.relatedNodes(badCells);
          return true;
        }
        return false;
      },
      deprecated: true
    }, {
      id: 'html5-scope',
      evaluate: function evaluate(node, options, virtualNode, context) {
        if (!axe.commons.dom.isHTML5(document)) {
          return true;
        }
        return node.nodeName.toUpperCase() === 'TH';
      }
    }, {
      id: 'same-caption-summary',
      evaluate: function evaluate(node, options, virtualNode, context) {
        return !!(node.summary && node.caption) && node.summary.toLowerCase() === axe.commons.text.accessibleText(node.caption).toLowerCase();
      }
    }, {
      id: 'scope-value',
      evaluate: function evaluate(node, options, virtualNode, context) {
        options = options || {};
        var value = node.getAttribute('scope').toLowerCase();
        var validVals = [ 'row', 'col', 'rowgroup', 'colgroup' ] || options.values;
        return validVals.indexOf(value) !== -1;
      }
    }, {
      id: 'td-has-header',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var tableUtils = axe.commons.table;
        var badCells = [];
        var cells = tableUtils.getAllCells(node);
        var tableGrid = tableUtils.toGrid(node);
        cells.forEach(function(cell) {
          if (axe.commons.dom.hasContent(cell) && tableUtils.isDataCell(cell) && !axe.commons.aria.label(cell)) {
            var hasHeaders = tableUtils.getHeaders(cell, tableGrid).some(function(header) {
              return header !== null && !!axe.commons.dom.hasContent(header);
            });
            if (!hasHeaders) {
              badCells.push(cell);
            }
          }
        });
        if (badCells.length) {
          this.relatedNodes(badCells);
          return false;
        }
        return true;
      }
    }, {
      id: 'td-headers-attr',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var cells = [];
        var reviewCells = [];
        var badCells = [];
        for (var rowIndex = 0; rowIndex < node.rows.length; rowIndex++) {
          var row = node.rows[rowIndex];
          for (var cellIndex = 0; cellIndex < row.cells.length; cellIndex++) {
            cells.push(row.cells[cellIndex]);
          }
        }
        var ids = cells.reduce(function(ids, cell) {
          if (cell.getAttribute('id')) {
            ids.push(cell.getAttribute('id'));
          }
          return ids;
        }, []);
        cells.forEach(function(cell) {
          var isSelf = false;
          var notOfTable = false;
          if (!cell.hasAttribute('headers')) {
            return;
          }
          var headersAttr = cell.getAttribute('headers').trim();
          if (!headersAttr) {
            return reviewCells.push(cell);
          }
          var headers = axe.utils.tokenList(headersAttr);
          if (headers.length !== 0) {
            if (cell.getAttribute('id')) {
              isSelf = headers.indexOf(cell.getAttribute('id').trim()) !== -1;
            }
            notOfTable = headers.some(function(header) {
              return !ids.includes(header);
            });
            if (isSelf || notOfTable) {
              badCells.push(cell);
            }
          }
        });
        if (badCells.length > 0) {
          this.relatedNodes(badCells);
          return false;
        }
        if (reviewCells.length) {
          this.relatedNodes(reviewCells);
          return undefined;
        }
        return true;
      }
    }, {
      id: 'th-has-data-cells',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var tableUtils = axe.commons.table;
        var cells = tableUtils.getAllCells(node);
        var checkResult = this;
        var reffedHeaders = [];
        cells.forEach(function(cell) {
          var headers = cell.getAttribute('headers');
          if (headers) {
            reffedHeaders = reffedHeaders.concat(headers.split(/\s+/));
          }
          var ariaLabel = cell.getAttribute('aria-labelledby');
          if (ariaLabel) {
            reffedHeaders = reffedHeaders.concat(ariaLabel.split(/\s+/));
          }
        });
        var headers = cells.filter(function(cell) {
          if (axe.commons.text.sanitize(cell.textContent) === '') {
            return false;
          }
          return cell.nodeName.toUpperCase() === 'TH' || [ 'rowheader', 'columnheader' ].indexOf(cell.getAttribute('role')) !== -1;
        });
        var tableGrid = tableUtils.toGrid(node);
        var out = true;
        headers.forEach(function(header) {
          if (header.getAttribute('id') && reffedHeaders.includes(header.getAttribute('id'))) {
            return;
          }
          var pos = tableUtils.getCellPosition(header, tableGrid);
          var hasCell = false;
          if (tableUtils.isColumnHeader(header)) {
            hasCell = tableUtils.traverse('down', pos, tableGrid).find(function(cell) {
              return !tableUtils.isColumnHeader(cell) && tableUtils.getHeaders(cell, tableGrid).includes(header);
            });
          }
          if (!hasCell && tableUtils.isRowHeader(header)) {
            hasCell = tableUtils.traverse('right', pos, tableGrid).find(function(cell) {
              return !tableUtils.isRowHeader(cell) && tableUtils.getHeaders(cell, tableGrid).includes(header);
            });
          }
          if (!hasCell) {
            checkResult.relatedNodes(header);
          }
          out = out && hasCell;
        });
        return out ? true : undefined;
      }
    }, {
      id: 'hidden-content',
      evaluate: function evaluate(node, options, virtualNode, context) {
        var whitelist = [ 'SCRIPT', 'HEAD', 'TITLE', 'NOSCRIPT', 'STYLE', 'TEMPLATE' ];
        if (!whitelist.includes(node.nodeName.toUpperCase()) && axe.commons.dom.hasContentVirtual(virtualNode)) {
          var styles = window.getComputedStyle(node);
          if (styles.getPropertyValue('display') === 'none') {
            return undefined;
          } else if (styles.getPropertyValue('visibility') === 'hidden') {
            var parent = axe.commons.dom.getComposedParent(node);
            var parentStyle = parent && window.getComputedStyle(parent);
            if (!parentStyle || parentStyle.getPropertyValue('visibility') !== 'hidden') {
              return undefined;
            }
          }
        }
        return true;
      }
    } ],
    commons: function() {
      var commons = {};
      var aria = commons.aria = {};
      var lookupTable = aria.lookupTable = {};
      var isNull = function isNull(value) {
        return value === null;
      };
      var isNotNull = function isNotNull(value) {
        return value !== null;
      };
      lookupTable.attributes = {
        'aria-activedescendant': {
          type: 'idref',
          allowEmpty: true,
          unsupported: false
        },
        'aria-atomic': {
          type: 'boolean',
          values: [ 'true', 'false' ],
          unsupported: false
        },
        'aria-autocomplete': {
          type: 'nmtoken',
          values: [ 'inline', 'list', 'both', 'none' ],
          unsupported: false
        },
        'aria-busy': {
          type: 'boolean',
          values: [ 'true', 'false' ],
          unsupported: false
        },
        'aria-checked': {
          type: 'nmtoken',
          values: [ 'true', 'false', 'mixed', 'undefined' ],
          unsupported: false
        },
        'aria-colcount': {
          type: 'int',
          unsupported: false
        },
        'aria-colindex': {
          type: 'int',
          unsupported: false
        },
        'aria-colspan': {
          type: 'int',
          unsupported: false
        },
        'aria-controls': {
          type: 'idrefs',
          allowEmpty: true,
          unsupported: false
        },
        'aria-current': {
          type: 'nmtoken',
          allowEmpty: true,
          values: [ 'page', 'step', 'location', 'date', 'time', 'true', 'false' ],
          unsupported: false
        },
        'aria-describedby': {
          type: 'idrefs',
          allowEmpty: true,
          unsupported: false
        },
        'aria-describedat': {
          unsupported: true,
          unstandardized: true
        },
        'aria-details': {
          type: 'idref',
          allowEmpty: true,
          unsupported: false
        },
        'aria-disabled': {
          type: 'boolean',
          values: [ 'true', 'false' ],
          unsupported: false
        },
        'aria-dropeffect': {
          type: 'nmtokens',
          values: [ 'copy', 'move', 'reference', 'execute', 'popup', 'none' ],
          unsupported: false
        },
        'aria-errormessage': {
          type: 'idref',
          allowEmpty: true,
          unsupported: false
        },
        'aria-expanded': {
          type: 'nmtoken',
          values: [ 'true', 'false', 'undefined' ],
          unsupported: false
        },
        'aria-flowto': {
          type: 'idrefs',
          allowEmpty: true,
          unsupported: false
        },
        'aria-grabbed': {
          type: 'nmtoken',
          values: [ 'true', 'false', 'undefined' ],
          unsupported: false
        },
        'aria-haspopup': {
          type: 'nmtoken',
          allowEmpty: true,
          values: [ 'true', 'false', 'menu', 'listbox', 'tree', 'grid', 'dialog' ],
          unsupported: false
        },
        'aria-hidden': {
          type: 'boolean',
          values: [ 'true', 'false' ],
          unsupported: false
        },
        'aria-invalid': {
          type: 'nmtoken',
          allowEmpty: true,
          values: [ 'true', 'false', 'spelling', 'grammar' ],
          unsupported: false
        },
        'aria-keyshortcuts': {
          type: 'string',
          allowEmpty: true,
          unsupported: false
        },
        'aria-label': {
          type: 'string',
          allowEmpty: true,
          unsupported: false
        },
        'aria-labelledby': {
          type: 'idrefs',
          allowEmpty: true,
          unsupported: false
        },
        'aria-level': {
          type: 'int',
          unsupported: false
        },
        'aria-live': {
          type: 'nmtoken',
          values: [ 'off', 'polite', 'assertive' ],
          unsupported: false
        },
        'aria-modal': {
          type: 'boolean',
          values: [ 'true', 'false' ],
          unsupported: false
        },
        'aria-multiline': {
          type: 'boolean',
          values: [ 'true', 'false' ],
          unsupported: false
        },
        'aria-multiselectable': {
          type: 'boolean',
          values: [ 'true', 'false' ],
          unsupported: false
        },
        'aria-orientation': {
          type: 'nmtoken',
          values: [ 'horizontal', 'vertical' ],
          unsupported: false
        },
        'aria-owns': {
          type: 'idrefs',
          allowEmpty: true,
          unsupported: false
        },
        'aria-placeholder': {
          type: 'string',
          allowEmpty: true,
          unsupported: false
        },
        'aria-posinset': {
          type: 'int',
          unsupported: false
        },
        'aria-pressed': {
          type: 'nmtoken',
          values: [ 'true', 'false', 'mixed', 'undefined' ],
          unsupported: false
        },
        'aria-readonly': {
          type: 'boolean',
          values: [ 'true', 'false' ],
          unsupported: false
        },
        'aria-relevant': {
          type: 'nmtokens',
          values: [ 'additions', 'removals', 'text', 'all' ],
          unsupported: false
        },
        'aria-required': {
          type: 'boolean',
          values: [ 'true', 'false' ],
          unsupported: false
        },
        'aria-roledescription': {
          type: 'string',
          allowEmpty: true,
          unsupported: false
        },
        'aria-rowcount': {
          type: 'int',
          unsupported: false
        },
        'aria-rowindex': {
          type: 'int',
          unsupported: false
        },
        'aria-rowspan': {
          type: 'int',
          unsupported: false
        },
        'aria-selected': {
          type: 'nmtoken',
          values: [ 'true', 'false', 'undefined' ],
          unsupported: false
        },
        'aria-setsize': {
          type: 'int',
          unsupported: false
        },
        'aria-sort': {
          type: 'nmtoken',
          values: [ 'ascending', 'descending', 'other', 'none' ],
          unsupported: false
        },
        'aria-valuemax': {
          type: 'decimal',
          unsupported: false
        },
        'aria-valuemin': {
          type: 'decimal',
          unsupported: false
        },
        'aria-valuenow': {
          type: 'decimal',
          unsupported: false
        },
        'aria-valuetext': {
          type: 'string',
          unsupported: false
        }
      };
      lookupTable.globalAttributes = [ 'aria-atomic', 'aria-busy', 'aria-controls', 'aria-current', 'aria-describedby', 'aria-details', 'aria-disabled', 'aria-dropeffect', 'aria-flowto', 'aria-grabbed', 'aria-haspopup', 'aria-hidden', 'aria-invalid', 'aria-keyshortcuts', 'aria-label', 'aria-labelledby', 'aria-live', 'aria-owns', 'aria-relevant', 'aria-roledescription' ];
      lookupTable.role = {
        alert: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        alertdialog: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-modal', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'dialog', 'section' ]
        },
        application: {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'article', 'audio', 'embed', 'iframe', 'object', 'section', 'svg', 'video' ]
        },
        article: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-posinset', 'aria-setsize', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'article' ],
          unsupported: false
        },
        banner: {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'header' ],
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        button: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-pressed', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          implicit: [ 'button', 'input[type="button"]', 'input[type="image"]', 'input[type="reset"]', 'input[type="submit"]', 'summary' ],
          unsupported: false,
          allowedElements: [ {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        cell: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-colindex', 'aria-colspan', 'aria-rowindex', 'aria-rowspan', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'row' ],
          implicit: [ 'td', 'th' ],
          unsupported: false
        },
        checkbox: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-checked', 'aria-required', 'aria-readonly', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          implicit: [ 'input[type="checkbox"]' ],
          unsupported: false,
          allowedElements: [ 'button' ]
        },
        columnheader: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-colindex', 'aria-colspan', 'aria-expanded', 'aria-rowindex', 'aria-rowspan', 'aria-required', 'aria-readonly', 'aria-selected', 'aria-sort', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'row' ],
          implicit: [ 'th' ],
          unsupported: false
        },
        combobox: {
          type: 'composite',
          attributes: {
            allowed: [ 'aria-autocomplete', 'aria-required', 'aria-activedescendant', 'aria-orientation', 'aria-errormessage' ],
            required: [ 'aria-expanded' ]
          },
          owned: {
            all: [ 'listbox', 'tree', 'grid', 'dialog', 'textbox' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ {
            nodeName: 'input',
            properties: {
              type: [ 'text', 'search', 'tel', 'url', 'email' ]
            }
          } ]
        },
        command: {
          nameFrom: [ 'author' ],
          type: 'abstract',
          unsupported: false
        },
        complementary: {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'aside' ],
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        composite: {
          nameFrom: [ 'author' ],
          type: 'abstract',
          unsupported: false
        },
        contentinfo: {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'footer' ],
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        definition: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'dd', 'dfn' ],
          unsupported: false
        },
        dialog: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-modal', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'dialog' ],
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        directory: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'ol', 'ul' ]
        },
        document: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'body' ],
          unsupported: false,
          allowedElements: [ 'article', 'embed', 'iframe', 'object', 'section', 'svg' ]
        },
        'doc-abstract': {
          type: 'section',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-acknowledgments': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-afterword': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-appendix': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-backlink': {
          type: 'link',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          unsupported: false,
          allowedElements: [ {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        'doc-biblioentry': {
          type: 'listitem',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-level', 'aria-posinset', 'aria-setsize', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: [ 'doc-bibliography' ],
          unsupported: false,
          allowedElements: [ 'li' ]
        },
        'doc-bibliography': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: {
            one: [ 'doc-biblioentry' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-biblioref': {
          type: 'link',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          unsupported: false,
          allowedElements: [ {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        'doc-chapter': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-colophon': {
          type: 'section',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-conclusion': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-cover': {
          type: 'img',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false
        },
        'doc-credit': {
          type: 'section',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-credits': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-dedication': {
          type: 'section',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-endnote': {
          type: 'listitem',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-level', 'aria-posinset', 'aria-setsize', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: [ 'doc-endnotes' ],
          unsupported: false,
          allowedElements: [ 'li' ]
        },
        'doc-endnotes': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: {
            one: [ 'doc-endnote' ]
          },
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-epigraph': {
          type: 'section',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false
        },
        'doc-epilogue': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-errata': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-example': {
          type: 'section',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'aside', 'section' ]
        },
        'doc-footnote': {
          type: 'section',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'aside', 'footer', 'header' ]
        },
        'doc-foreword': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-glossary': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: [ 'term', 'definition' ],
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'dl' ]
        },
        'doc-glossref': {
          type: 'link',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author', 'contents' ],
          context: null,
          unsupported: false,
          allowedElements: [ {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        'doc-index': {
          type: 'navigation',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'nav', 'section' ]
        },
        'doc-introduction': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-noteref': {
          type: 'link',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author', 'contents' ],
          context: null,
          unsupported: false,
          allowedElements: [ {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        'doc-notice': {
          type: 'note',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-pagebreak': {
          type: 'separator',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'hr' ]
        },
        'doc-pagelist': {
          type: 'navigation',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'nav', 'section' ]
        },
        'doc-part': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-preface': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-prologue': {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-pullquote': {
          type: 'none',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'aside', 'section' ]
        },
        'doc-qna': {
          type: 'section',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        'doc-subtitle': {
          type: 'sectionhead',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: {
            nodeName: [ 'h1', 'h2', 'h3', 'h4', 'h5', 'h6' ]
          }
        },
        'doc-tip': {
          type: 'note',
          attributes: {
            allowed: [ 'aria-expanded' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'aside' ]
        },
        'doc-toc': {
          type: 'navigation',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          namefrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'nav', 'section' ]
        },
        feed: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: {
            one: [ 'article' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'article', 'aside', 'section' ]
        },
        figure: {
          type: 'structure',
          unsupported: false
        },
        form: {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'form' ],
          unsupported: false
        },
        grid: {
          type: 'composite',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-expanded', 'aria-colcount', 'aria-level', 'aria-multiselectable', 'aria-readonly', 'aria-rowcount', 'aria-errormessage' ]
          },
          owned: {
            one: [ 'rowgroup', 'row' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'table' ],
          unsupported: false
        },
        gridcell: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-colindex', 'aria-colspan', 'aria-expanded', 'aria-rowindex', 'aria-rowspan', 'aria-selected', 'aria-readonly', 'aria-required', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'row' ],
          implicit: [ 'td', 'th' ],
          unsupported: false
        },
        group: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'details', 'optgroup' ],
          unsupported: false,
          allowedElements: [ 'dl', 'figcaption', 'fieldset', 'figure', 'footer', 'header', 'ol', 'ul' ]
        },
        heading: {
          type: 'structure',
          attributes: {
            required: [ 'aria-level' ],
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          implicit: [ 'h1', 'h2', 'h3', 'h4', 'h5', 'h6' ],
          unsupported: false
        },
        img: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'img' ],
          unsupported: false,
          allowedElements: [ 'embed', 'iframe', 'object', 'svg' ]
        },
        input: {
          nameFrom: [ 'author' ],
          type: 'abstract',
          unsupported: false
        },
        landmark: {
          nameFrom: [ 'author' ],
          type: 'abstract',
          unsupported: false
        },
        link: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          implicit: [ 'a[href]' ],
          unsupported: false,
          allowedElements: [ 'button', {
            nodeName: 'input',
            properties: {
              type: [ 'image', 'button' ]
            }
          } ]
        },
        list: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: {
            all: [ 'listitem' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'ol', 'ul', 'dl' ],
          unsupported: false
        },
        listbox: {
          type: 'composite',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-multiselectable', 'aria-readonly', 'aria-required', 'aria-expanded', 'aria-orientation', 'aria-errormessage' ]
          },
          owned: {
            all: [ 'option' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'select' ],
          unsupported: false,
          allowedElements: [ 'ol', 'ul' ]
        },
        listitem: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-level', 'aria-posinset', 'aria-setsize', 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'list' ],
          implicit: [ 'li', 'dt' ],
          unsupported: false
        },
        log: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        main: {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'main' ],
          unsupported: false,
          allowedElements: [ 'article', 'section' ]
        },
        marquee: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        math: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'math' ],
          unsupported: false
        },
        menu: {
          type: 'composite',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-expanded', 'aria-orientation', 'aria-errormessage' ]
          },
          owned: {
            one: [ 'menuitem', 'menuitemradio', 'menuitemcheckbox' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'menu[type="context"]' ],
          unsupported: false,
          allowedElements: [ 'ol', 'ul' ]
        },
        menubar: {
          type: 'composite',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-expanded', 'aria-orientation', 'aria-errormessage' ]
          },
          owned: {
            one: [ 'menuitem', 'menuitemradio', 'menuitemcheckbox' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'ol', 'ul' ]
        },
        menuitem: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-posinset', 'aria-setsize', 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'menu', 'menubar' ],
          implicit: [ 'menuitem[type="command"]' ],
          unsupported: false,
          allowedElements: [ 'button', 'li', {
            nodeName: 'iput',
            properties: {
              type: [ 'image', 'button' ]
            }
          }, {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        menuitemcheckbox: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-checked', 'aria-posinset', 'aria-setsize', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'menu', 'menubar' ],
          implicit: [ 'menuitem[type="checkbox"]' ],
          unsupported: false,
          allowedElements: [ {
            nodeName: [ 'button', 'li' ]
          }, {
            nodeName: 'input',
            properties: {
              type: [ 'checkbox', 'image', 'button' ]
            }
          }, {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        menuitemradio: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-checked', 'aria-selected', 'aria-posinset', 'aria-setsize', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'menu', 'menubar' ],
          implicit: [ 'menuitem[type="radio"]' ],
          unsupported: false,
          allowedElements: [ {
            nodeName: [ 'button', 'li' ]
          }, {
            nodeName: 'input',
            properties: {
              type: [ 'image', 'button', 'radio' ]
            }
          }, {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        navigation: {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'nav' ],
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        none: {
          type: 'structure',
          attributes: null,
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ {
            nodeName: [ 'article', 'aside', 'dl', 'embed', 'figcaption', 'fieldset', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'iframe', 'li', 'ol', 'section', 'ul' ]
          }, {
            nodeName: 'img',
            attributes: {
              alt: isNotNull
            }
          } ]
        },
        note: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'aside' ]
        },
        option: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-selected', 'aria-posinset', 'aria-setsize', 'aria-checked', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'listbox' ],
          implicit: [ 'option' ],
          unsupported: false,
          allowedElements: [ {
            nodeName: [ 'button', 'li' ]
          }, {
            nodeName: 'input',
            properties: {
              type: [ 'checkbox', 'button' ]
            }
          }, {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        presentation: {
          type: 'structure',
          attributes: null,
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ {
            nodeName: [ 'article', 'aside', 'dl', 'embed', 'figcaption', 'fieldset', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'iframe', 'li', 'ol', 'section', 'ul' ]
          }, {
            nodeName: 'img',
            attributes: {
              alt: isNotNull
            }
          } ]
        },
        progressbar: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-valuetext', 'aria-valuenow', 'aria-valuemax', 'aria-valuemin', 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'progress' ],
          unsupported: false
        },
        radio: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-selected', 'aria-posinset', 'aria-setsize', 'aria-required', 'aria-errormessage', 'aria-checked' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          implicit: [ 'input[type="radio"]' ],
          unsupported: false,
          allowedElements: [ {
            nodeName: [ 'button', 'li' ]
          }, {
            nodeName: 'input',
            properties: {
              type: [ 'image', 'button' ]
            }
          } ]
        },
        radiogroup: {
          type: 'composite',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-required', 'aria-expanded', 'aria-readonly', 'aria-errormessage' ]
          },
          owned: {
            all: [ 'radio' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: {
            nodeName: [ 'ol', 'ul' ]
          }
        },
        range: {
          nameFrom: [ 'author' ],
          type: 'abstract',
          unsupported: false
        },
        region: {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'section[aria-label]', 'section[aria-labelledby]', 'section[title]' ],
          unsupported: false,
          allowedElements: {
            nodeName: [ 'article', 'aside' ]
          }
        },
        roletype: {
          type: 'abstract',
          unsupported: false
        },
        row: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-colindex', 'aria-expanded', 'aria-level', 'aria-selected', 'aria-rowindex', 'aria-errormessage' ]
          },
          owned: {
            one: [ 'cell', 'columnheader', 'rowheader', 'gridcell' ]
          },
          nameFrom: [ 'author', 'contents' ],
          context: [ 'rowgroup', 'grid', 'treegrid', 'table' ],
          implicit: [ 'tr' ],
          unsupported: false
        },
        rowgroup: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-expanded', 'aria-errormessage' ]
          },
          owned: {
            all: [ 'row' ]
          },
          nameFrom: [ 'author', 'contents' ],
          context: [ 'grid', 'table', 'treegrid' ],
          implicit: [ 'tbody', 'thead', 'tfoot' ],
          unsupported: false
        },
        rowheader: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-colindex', 'aria-colspan', 'aria-expanded', 'aria-rowindex', 'aria-rowspan', 'aria-required', 'aria-readonly', 'aria-selected', 'aria-sort', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'row' ],
          implicit: [ 'th' ],
          unsupported: false
        },
        scrollbar: {
          type: 'widget',
          attributes: {
            required: [ 'aria-controls', 'aria-valuenow' ],
            allowed: [ 'aria-valuetext', 'aria-orientation', 'aria-errormessage', 'aria-valuemax', 'aria-valuemin' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false
        },
        search: {
          type: 'landmark',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: {
            nodeName: [ 'aside', 'form', 'section' ]
          }
        },
        searchbox: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-autocomplete', 'aria-multiline', 'aria-readonly', 'aria-required', 'aria-placeholder', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'input[type="search"]' ],
          unsupported: false,
          allowedElements: {
            nodeName: 'input',
            properties: {
              type: 'text'
            }
          }
        },
        section: {
          nameFrom: [ 'author', 'contents' ],
          type: 'abstract',
          unsupported: false
        },
        sectionhead: {
          nameFrom: [ 'author', 'contents' ],
          type: 'abstract',
          unsupported: false
        },
        select: {
          nameFrom: [ 'author' ],
          type: 'abstract',
          unsupported: false
        },
        separator: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-orientation', 'aria-valuenow', 'aria-valuemax', 'aria-valuemin', 'aria-valuetext', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'hr' ],
          unsupported: false,
          allowedElements: [ 'li' ]
        },
        slider: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-valuetext', 'aria-orientation', 'aria-readonly', 'aria-errormessage', 'aria-valuemax', 'aria-valuemin' ],
            required: [ 'aria-valuenow' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'input[type="range"]' ],
          unsupported: false
        },
        spinbutton: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-valuetext', 'aria-required', 'aria-readonly', 'aria-errormessage', 'aria-valuemax', 'aria-valuemin' ],
            required: [ 'aria-valuenow' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'input[type="number"]' ],
          unsupported: false,
          allowedElements: {
            nodeName: 'input',
            properties: {
              type: [ 'text', 'tel' ]
            }
          }
        },
        status: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'output' ],
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        structure: {
          type: 'abstract',
          unsupported: false
        },
        switch: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-errormessage' ],
            required: [ 'aria-checked' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'button', {
            nodeName: 'input',
            properties: {
              type: [ 'checkbox', 'image', 'button' ]
            }
          }, {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        tab: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-selected', 'aria-expanded', 'aria-setsize', 'aria-posinset', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'tablist' ],
          unsupported: false,
          allowedElements: [ {
            nodeName: [ 'button', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li' ]
          }, {
            nodeName: 'input',
            properties: {
              type: 'button'
            }
          }, {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        table: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-colcount', 'aria-rowcount', 'aria-errormessage' ]
          },
          owned: {
            one: [ 'rowgroup', 'row' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'table' ],
          unsupported: false
        },
        tablist: {
          type: 'composite',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-expanded', 'aria-level', 'aria-multiselectable', 'aria-orientation', 'aria-errormessage' ]
          },
          owned: {
            all: [ 'tab' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'ol', 'ul' ]
        },
        tabpanel: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'section' ]
        },
        term: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          implicit: [ 'dt' ],
          unsupported: false
        },
        textbox: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-autocomplete', 'aria-multiline', 'aria-readonly', 'aria-required', 'aria-placeholder', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'input[type="text"]', 'input[type="email"]', 'input[type="password"]', 'input[type="tel"]', 'input[type="url"]', 'input:not([type])', 'textarea' ],
          unsupported: false
        },
        timer: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false
        },
        toolbar: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-expanded', 'aria-orientation', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author' ],
          context: null,
          implicit: [ 'menu[type="toolbar"]' ],
          unsupported: false,
          allowedElements: [ 'ol', 'ul' ]
        },
        tooltip: {
          type: 'structure',
          attributes: {
            allowed: [ 'aria-expanded', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: null,
          unsupported: false
        },
        tree: {
          type: 'composite',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-multiselectable', 'aria-required', 'aria-expanded', 'aria-orientation', 'aria-errormessage' ]
          },
          owned: {
            all: [ 'treeitem' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false,
          allowedElements: [ 'ol', 'ul' ]
        },
        treegrid: {
          type: 'composite',
          attributes: {
            allowed: [ 'aria-activedescendant', 'aria-colcount', 'aria-expanded', 'aria-level', 'aria-multiselectable', 'aria-readonly', 'aria-required', 'aria-rowcount', 'aria-orientation', 'aria-errormessage' ]
          },
          owned: {
            one: [ 'rowgroup', 'row' ]
          },
          nameFrom: [ 'author' ],
          context: null,
          unsupported: false
        },
        treeitem: {
          type: 'widget',
          attributes: {
            allowed: [ 'aria-checked', 'aria-selected', 'aria-expanded', 'aria-level', 'aria-posinset', 'aria-setsize', 'aria-errormessage' ]
          },
          owned: null,
          nameFrom: [ 'author', 'contents' ],
          context: [ 'group', 'tree' ],
          unsupported: false,
          allowedElements: [ 'li', {
            nodeName: 'a',
            attributes: {
              href: isNotNull
            }
          } ]
        },
        widget: {
          type: 'abstract',
          unsupported: false
        },
        window: {
          nameFrom: [ 'author' ],
          type: 'abstract',
          unsupported: false
        }
      };
      lookupTable.elementsAllowedNoRole = [ {
        nodeName: [ 'base', 'body', 'caption', 'col', 'colgroup', 'datalist', 'dd', 'details', 'dt', 'head', 'html', 'keygen', 'label', 'legend', 'main', 'map', 'math', 'meta', 'meter', 'noscript', 'optgroup', 'param', 'picture', 'progress', 'script', 'source', 'style', 'template', 'textarea', 'title', 'track' ]
      }, {
        nodeName: 'area',
        attributes: {
          href: isNotNull
        }
      }, {
        nodeName: 'input',
        properties: {
          type: [ 'color', 'data', 'datatime', 'file', 'hidden', 'month', 'number', 'password', 'range', 'reset', 'submit', 'time', 'week' ]
        }
      }, {
        nodeName: 'link',
        attributes: {
          href: isNotNull
        }
      }, {
        nodeName: 'menu',
        attributes: {
          type: 'context'
        }
      }, {
        nodeName: 'menuitem',
        attributes: {
          type: [ 'command', 'checkbox', 'radio' ]
        }
      }, {
        nodeName: 'select',
        condition: function condition(vNode) {
          if (!(vNode instanceof axe.AbstractVirtualNode)) {
            vNode = axe.utils.getNodeFromTree(vNode);
          }
          return Number(vNode.attr('size')) > 1;
        },
        properties: {
          multiple: true
        }
      }, {
        nodeName: [ 'clippath', 'cursor', 'defs', 'desc', 'feblend', 'fecolormatrix', 'fecomponenttransfer', 'fecomposite', 'feconvolvematrix', 'fediffuselighting', 'fedisplacementmap', 'fedistantlight', 'fedropshadow', 'feflood', 'fefunca', 'fefuncb', 'fefuncg', 'fefuncr', 'fegaussianblur', 'feimage', 'femerge', 'femergenode', 'femorphology', 'feoffset', 'fepointlight', 'fespecularlighting', 'fespotlight', 'fetile', 'feturbulence', 'filter', 'hatch', 'hatchpath', 'lineargradient', 'marker', 'mask', 'meshgradient', 'meshpatch', 'meshrow', 'metadata', 'mpath', 'pattern', 'radialgradient', 'solidcolor', 'stop', 'switch', 'view' ]
      } ];
      lookupTable.elementsAllowedAnyRole = [ {
        nodeName: 'a',
        attributes: {
          href: isNull
        }
      }, {
        nodeName: 'img',
        attributes: {
          alt: isNull
        }
      }, {
        nodeName: [ 'abbr', 'address', 'canvas', 'div', 'p', 'pre', 'blockquote', 'ins', 'del', 'output', 'span', 'table', 'tbody', 'thead', 'tfoot', 'td', 'em', 'strong', 'small', 's', 'cite', 'q', 'dfn', 'abbr', 'time', 'code', 'var', 'samp', 'kbd', 'sub', 'sup', 'i', 'b', 'u', 'mark', 'ruby', 'rt', 'rp', 'bdi', 'bdo', 'br', 'wbr', 'th', 'tr' ]
      } ];
      lookupTable.evaluateRoleForElement = {
        A: function A(_ref24) {
          var node = _ref24.node, out = _ref24.out;
          if (node.namespaceURI === 'http://www.w3.org/2000/svg') {
            return true;
          }
          if (node.href.length) {
            return out;
          }
          return true;
        },
        AREA: function AREA(_ref25) {
          var node = _ref25.node;
          return !node.href;
        },
        BUTTON: function BUTTON(_ref26) {
          var node = _ref26.node, role = _ref26.role, out = _ref26.out;
          if (node.getAttribute('type') === 'menu') {
            return role === 'menuitem';
          }
          return out;
        },
        IMG: function IMG(_ref27) {
          var node = _ref27.node, role = _ref27.role, out = _ref27.out;
          switch (node.alt) {
           case null:
            return out;

           case '':
            return role === 'presentation' || role === 'none';

           default:
            return role !== 'presentation' && role !== 'none';
          }
        },
        INPUT: function INPUT(_ref28) {
          var node = _ref28.node, role = _ref28.role, out = _ref28.out;
          switch (node.type) {
           case 'button':
           case 'image':
            return out;

           case 'checkbox':
            if (role === 'button' && node.hasAttribute('aria-pressed')) {
              return true;
            }
            return out;

           case 'radio':
            return role === 'menuitemradio';

           case 'text':
            return role === 'combobox' || role === 'searchbox' || role === 'spinbutton';

           case 'tel':
            return role === 'combobox' || role === 'spinbutton';

           case 'url':
           case 'search':
           case 'email':
            return role === 'combobox';

           default:
            return false;
          }
        },
        LI: function LI(_ref29) {
          var node = _ref29.node, out = _ref29.out;
          var hasImplicitListitemRole = axe.utils.matchesSelector(node, 'ol li, ul li');
          if (hasImplicitListitemRole) {
            return out;
          }
          return true;
        },
        MENU: function MENU(_ref30) {
          var node = _ref30.node;
          if (node.getAttribute('type') === 'context') {
            return false;
          }
          return true;
        },
        OPTION: function OPTION(_ref31) {
          var node = _ref31.node;
          var withinOptionList = axe.utils.matchesSelector(node, 'select > option, datalist > option, optgroup > option');
          return !withinOptionList;
        },
        SELECT: function SELECT(_ref32) {
          var node = _ref32.node, role = _ref32.role;
          return !node.multiple && node.size <= 1 && role === 'menu';
        },
        SVG: function SVG(_ref33) {
          var node = _ref33.node, out = _ref33.out;
          if (node.parentNode && node.parentNode.namespaceURI === 'http://www.w3.org/2000/svg') {
            return true;
          }
          return out;
        }
      };
      lookupTable.rolesOfType = {
        widget: [ 'button', 'checkbox', 'dialog', 'gridcell', 'link', 'log', 'marquee', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'option', 'progressbar', 'radio', 'scrollbar', 'searchbox', 'slider', 'spinbutton', 'status', 'switch', 'tab', 'tabpanel', 'textbox', 'timer', 'tooltip', 'tree', 'treeitem' ]
      };
      var color = {};
      commons.color = color;
      var dom = commons.dom = {};
      var forms = {};
      commons.forms = forms;
      function matches(vNode, definition) {
        return matches.fromDefinition(vNode, definition);
      }
      commons.matches = matches;
      var table = commons.table = {};
      var text = commons.text = {
        EdgeFormDefaults: {}
      };
      var utils = commons.utils = axe.utils;
      aria.arialabelText = function arialabelText(node) {
        if (node instanceof axe.AbstractVirtualNode === false) {
          if (node.nodeType !== 1) {
            return '';
          }
          node = axe.utils.getNodeFromTree(node);
        }
        return node.attr('aria-label') || '';
      };
      aria.arialabelledbyText = function arialabelledbyText(node) {
        var context = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
        node = node.actualNode || node;
        if (node.nodeType !== 1 || context.inLabelledByContext || context.inControlContext) {
          return '';
        }
        var refs = dom.idrefs(node, 'aria-labelledby').filter(function(elm) {
          return elm;
        });
        return refs.reduce(function(accessibleName, elm) {
          var accessibleNameAdd = text.accessibleText(elm, _extends({
            inLabelledByContext: true,
            startNode: context.startNode || node
          }, context));
          if (!accessibleName) {
            return accessibleNameAdd;
          } else {
            return ''.concat(accessibleName, ' ').concat(accessibleNameAdd);
          }
        }, '');
      };
      aria.requiredAttr = function(role) {
        var roles = aria.lookupTable.role[role], attr = roles && roles.attributes && roles.attributes.required;
        return attr || [];
      };
      aria.allowedAttr = function(role) {
        var roles = aria.lookupTable.role[role], attr = roles && roles.attributes && roles.attributes.allowed || [], requiredAttr = roles && roles.attributes && roles.attributes.required || [];
        return attr.concat(aria.lookupTable.globalAttributes).concat(requiredAttr);
      };
      aria.validateAttr = function validateAttr(att) {
        var attrDefinition = aria.lookupTable.attributes[att];
        return !!attrDefinition;
      };
      var dpubRoles = [ 'doc-backlink', 'doc-biblioentry', 'doc-biblioref', 'doc-cover', 'doc-endnote', 'doc-glossref', 'doc-noteref' ];
      function getRoleSegments(node) {
        var roles = [];
        if (!node) {
          return roles;
        }
        if (node.hasAttribute('role')) {
          var nodeRoles = axe.utils.tokenList(node.getAttribute('role').toLowerCase());
          roles = roles.concat(nodeRoles);
        }
        if (node.hasAttributeNS('http://www.idpf.org/2007/ops', 'type')) {
          var epubRoles = axe.utils.tokenList(node.getAttributeNS('http://www.idpf.org/2007/ops', 'type').toLowerCase()).map(function(role) {
            return 'doc-'.concat(role);
          });
          roles = roles.concat(epubRoles);
        }
        roles = roles.filter(function(role) {
          return axe.commons.aria.isValidRole(role);
        });
        return roles;
      }
      aria.getElementUnallowedRoles = function getElementUnallowedRoles(node) {
        var allowImplicit = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : true;
        var tagName = node.nodeName.toUpperCase();
        if (!axe.utils.isHtmlElement(node)) {
          return [];
        }
        var roleSegments = getRoleSegments(node);
        var implicitRole = axe.commons.aria.implicitRole(node);
        var unallowedRoles = roleSegments.filter(function(role) {
          if (allowImplicit && role === implicitRole) {
            return false;
          }
          if (allowImplicit && dpubRoles.includes(role)) {
            var roleType = axe.commons.aria.getRoleType(role);
            if (implicitRole !== roleType) {
              return true;
            }
          }
          if (!allowImplicit && !(role === 'row' && tagName === 'TR' && axe.utils.matchesSelector(node, 'table[role="grid"] > tr'))) {
            return true;
          }
          return !aria.isAriaRoleAllowedOnElement(node, role);
        });
        return unallowedRoles;
      };
      aria.getOwnedVirtual = function getOwned(_ref34) {
        var actualNode = _ref34.actualNode, children = _ref34.children;
        if (!actualNode || !children) {
          throw new Error('getOwnedVirtual requires a virtual node');
        }
        return dom.idrefs(actualNode, 'aria-owns').reduce(function(ownedElms, element) {
          if (element) {
            var virtualNode = axe.utils.getNodeFromTree(element);
            ownedElms.push(virtualNode);
          }
          return ownedElms;
        }, children);
      };
      aria.getRole = function getRole(node) {
        var _ref35 = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {}, noImplicit = _ref35.noImplicit, fallback = _ref35.fallback, abstracts = _ref35.abstracts, dpub = _ref35.dpub;
        node = node.actualNode || node;
        if (node.nodeType !== 1) {
          return null;
        }
        var roleAttr = (node.getAttribute('role') || '').trim().toLowerCase();
        var roleList = fallback ? axe.utils.tokenList(roleAttr) : [ roleAttr ];
        var validRoles = roleList.filter(function(role) {
          if (!dpub && role.substr(0, 4) === 'doc-') {
            return false;
          }
          return aria.isValidRole(role, {
            allowAbstract: abstracts
          });
        });
        var explicitRole = validRoles[0];
        if (!explicitRole && !noImplicit) {
          return aria.implicitRole(node);
        }
        return explicitRole || null;
      };
      var idRefsRegex = /^idrefs?$/;
      function cacheIdRefs(node, refAttrs) {
        if (node.hasAttribute) {
          var idRefs = axe._cache.get('idRefs');
          if (node.nodeName.toUpperCase() === 'LABEL' && node.hasAttribute('for')) {
            idRefs[node.getAttribute('for')] = true;
          }
          for (var i = 0; i < refAttrs.length; ++i) {
            var attr = refAttrs[i];
            if (!node.hasAttribute(attr)) {
              continue;
            }
            var attrValue = node.getAttribute(attr);
            var tokens = axe.utils.tokenList(attrValue);
            for (var k = 0; k < tokens.length; ++k) {
              idRefs[tokens[k]] = true;
            }
          }
        }
        for (var _i3 = 0; _i3 < node.children.length; _i3++) {
          cacheIdRefs(node.children[_i3], refAttrs);
        }
      }
      aria.isAccessibleRef = function isAccessibleRef(node) {
        node = node.actualNode || node;
        var root = dom.getRootNode(node);
        root = root.documentElement || root;
        var id = node.id;
        if (!axe._cache.get('idRefs')) {
          axe._cache.set('idRefs', {});
          var refAttrs = Object.keys(aria.lookupTable.attributes).filter(function(attr) {
            var type = aria.lookupTable.attributes[attr].type;
            return idRefsRegex.test(type);
          });
          cacheIdRefs(root, refAttrs);
        }
        return axe._cache.get('idRefs')[id] === true;
      };
      aria.isAriaRoleAllowedOnElement = function isAriaRoleAllowedOnElement(node, role) {
        var nodeName = node.nodeName.toUpperCase();
        var lookupTable = axe.commons.aria.lookupTable;
        if (matches(node, lookupTable.elementsAllowedNoRole)) {
          return false;
        }
        if (matches(node, lookupTable.elementsAllowedAnyRole)) {
          return true;
        }
        var roleValue = lookupTable.role[role];
        if (!roleValue || !roleValue.allowedElements) {
          return false;
        }
        var out = matches(node, roleValue.allowedElements);
        if (Object.keys(lookupTable.evaluateRoleForElement).includes(nodeName)) {
          return lookupTable.evaluateRoleForElement[nodeName]({
            node: node,
            role: role,
            out: out
          });
        }
        return out;
      };
      aria.isUnsupportedRole = function(role) {
        var roleDefinition = aria.lookupTable.role[role];
        return roleDefinition ? roleDefinition.unsupported : false;
      };
      aria.labelVirtual = function(_ref36) {
        var actualNode = _ref36.actualNode;
        var ref, candidate;
        if (actualNode.getAttribute('aria-labelledby')) {
          ref = dom.idrefs(actualNode, 'aria-labelledby');
          candidate = ref.map(function(thing) {
            var vNode = axe.utils.getNodeFromTree(thing);
            return vNode ? text.visibleVirtual(vNode, true) : '';
          }).join(' ').trim();
          if (candidate) {
            return candidate;
          }
        }
        candidate = actualNode.getAttribute('aria-label');
        if (candidate) {
          candidate = text.sanitize(candidate).trim();
          if (candidate) {
            return candidate;
          }
        }
        return null;
      };
      aria.label = function(node) {
        node = axe.utils.getNodeFromTree(node);
        return aria.labelVirtual(node);
      };
      aria.namedFromContents = function namedFromContents(node) {
        var _ref37 = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {}, strict = _ref37.strict;
        node = node.actualNode || node;
        if (node.nodeType !== 1) {
          return false;
        }
        var role = aria.getRole(node);
        var roleDef = aria.lookupTable.role[role];
        if (roleDef && roleDef.nameFrom.includes('contents') || node.nodeName.toUpperCase() === 'TABLE') {
          return true;
        }
        if (strict) {
          return false;
        }
        return !roleDef || [ 'presentation', 'none' ].includes(role);
      };
      aria.isValidRole = function(role) {
        var _ref38 = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {}, allowAbstract = _ref38.allowAbstract, _ref38$flagUnsupporte = _ref38.flagUnsupported, flagUnsupported = _ref38$flagUnsupporte === void 0 ? false : _ref38$flagUnsupporte;
        var roleDefinition = aria.lookupTable.role[role];
        var isRoleUnsupported = roleDefinition ? roleDefinition.unsupported : false;
        if (!roleDefinition || flagUnsupported && isRoleUnsupported) {
          return false;
        }
        return allowAbstract ? true : roleDefinition.type !== 'abstract';
      };
      aria.getRolesWithNameFromContents = function() {
        return Object.keys(aria.lookupTable.role).filter(function(r) {
          return aria.lookupTable.role[r].nameFrom && aria.lookupTable.role[r].nameFrom.indexOf('contents') !== -1;
        });
      };
      aria.getRolesByType = function(roleType) {
        return Object.keys(aria.lookupTable.role).filter(function(r) {
          return aria.lookupTable.role[r].type === roleType;
        });
      };
      aria.getRoleType = function(role) {
        var r = aria.lookupTable.role[role];
        return r && r.type || null;
      };
      aria.requiredOwned = function(role) {
        'use strict';
        var owned = null, roles = aria.lookupTable.role[role];
        if (roles) {
          owned = axe.utils.clone(roles.owned);
        }
        return owned;
      };
      aria.requiredContext = function(role) {
        'use strict';
        var context = null, roles = aria.lookupTable.role[role];
        if (roles) {
          context = axe.utils.clone(roles.context);
        }
        return context;
      };
      aria.implicitNodes = function(role) {
        'use strict';
        var implicit = null, roles = aria.lookupTable.role[role];
        if (roles && roles.implicit) {
          implicit = axe.utils.clone(roles.implicit);
        }
        return implicit;
      };
      aria.implicitRole = function(node) {
        'use strict';
        var isValidImplicitRole = function isValidImplicitRole(set, role) {
          var validForNodeType = function validForNodeType(implicitNodeTypeSelector) {
            return axe.utils.matchesSelector(node, implicitNodeTypeSelector);
          };
          if (role.implicit && role.implicit.some(validForNodeType)) {
            set.push(role.name);
          }
          return set;
        };
        var sortRolesByOptimalAriaContext = function sortRolesByOptimalAriaContext(roles, ariaAttributes) {
          var getScore = function getScore(role) {
            var allowedAriaAttributes = aria.allowedAttr(role);
            return allowedAriaAttributes.reduce(function(score, attribute) {
              return score + (ariaAttributes.indexOf(attribute) > -1 ? 1 : 0);
            }, 0);
          };
          var scored = roles.map(function(role) {
            return {
              score: getScore(role),
              name: role
            };
          });
          var sorted = scored.sort(function(scoredRoleA, scoredRoleB) {
            return scoredRoleB.score - scoredRoleA.score;
          });
          return sorted.map(function(sortedRole) {
            return sortedRole.name;
          });
        };
        var roles = Object.keys(aria.lookupTable.role).map(function(role) {
          var lookup = aria.lookupTable.role[role];
          return {
            name: role,
            implicit: lookup && lookup.implicit
          };
        });
        var availableImplicitRoles = roles.reduce(isValidImplicitRole, []);
        if (!availableImplicitRoles.length) {
          return null;
        }
        var nodeAttributes = axe.utils.getNodeAttributes(node);
        var ariaAttributes = [];
        for (var i = 0, j = nodeAttributes.length; i < j; i++) {
          var attr = nodeAttributes[i];
          if (attr.name.match(/^aria-/)) {
            ariaAttributes.push(attr.name);
          }
        }
        return sortRolesByOptimalAriaContext(availableImplicitRoles, ariaAttributes).shift();
      };
      aria.validateAttrValue = function validateAttrValue(node, attr) {
        'use strict';
        var matches, list, value = node.getAttribute(attr), attrInfo = aria.lookupTable.attributes[attr];
        var doc = dom.getRootNode(node);
        if (!attrInfo) {
          return true;
        }
        if (attrInfo.allowEmpty && (!value || value.trim() === '')) {
          return true;
        }
        switch (attrInfo.type) {
         case 'boolean':
         case 'nmtoken':
          return typeof value === 'string' && attrInfo.values.includes(value.toLowerCase());

         case 'nmtokens':
          list = axe.utils.tokenList(value);
          return list.reduce(function(result, token) {
            return result && attrInfo.values.includes(token);
          }, list.length !== 0);

         case 'idref':
          return !!(value && doc.getElementById(value));

         case 'idrefs':
          list = axe.utils.tokenList(value);
          return list.some(function(token) {
            return doc.getElementById(token);
          });

         case 'string':
          return value.trim() !== '';

         case 'decimal':
          matches = value.match(/^[-+]?([0-9]*)\.?([0-9]*)$/);
          return !!(matches && (matches[1] || matches[2]));

         case 'int':
          return /^[-+]?[0-9]+$/.test(value);
        }
      };
      color.centerPointOfRect = function centerPointOfRect(rect) {
        if (rect.left > window.innerWidth) {
          return undefined;
        }
        if (rect.top > window.innerHeight) {
          return undefined;
        }
        var x = Math.min(Math.ceil(rect.left + rect.width / 2), window.innerWidth - 1);
        var y = Math.min(Math.ceil(rect.top + rect.height / 2), window.innerHeight - 1);
        return {
          x: x,
          y: y
        };
      };
      color.Color = function(red, green, blue, alpha) {
        this.red = red;
        this.green = green;
        this.blue = blue;
        this.alpha = alpha;
        this.toHexString = function() {
          var redString = Math.round(this.red).toString(16);
          var greenString = Math.round(this.green).toString(16);
          var blueString = Math.round(this.blue).toString(16);
          return '#' + (this.red > 15.5 ? redString : '0' + redString) + (this.green > 15.5 ? greenString : '0' + greenString) + (this.blue > 15.5 ? blueString : '0' + blueString);
        };
        var rgbRegex = /^rgb\((\d+), (\d+), (\d+)\)$/;
        var rgbaRegex = /^rgba\((\d+), (\d+), (\d+), (\d*(\.\d+)?)\)/;
        this.parseRgbString = function(colorString) {
          if (colorString === 'transparent') {
            this.red = 0;
            this.green = 0;
            this.blue = 0;
            this.alpha = 0;
            return;
          }
          var match = colorString.match(rgbRegex);
          if (match) {
            this.red = parseInt(match[1], 10);
            this.green = parseInt(match[2], 10);
            this.blue = parseInt(match[3], 10);
            this.alpha = 1;
            return;
          }
          match = colorString.match(rgbaRegex);
          if (match) {
            this.red = parseInt(match[1], 10);
            this.green = parseInt(match[2], 10);
            this.blue = parseInt(match[3], 10);
            this.alpha = Math.round(parseFloat(match[4]) * 100) / 100;
            return;
          }
        };
        this.getRelativeLuminance = function() {
          var rSRGB = this.red / 255;
          var gSRGB = this.green / 255;
          var bSRGB = this.blue / 255;
          var r = rSRGB <= .03928 ? rSRGB / 12.92 : Math.pow((rSRGB + .055) / 1.055, 2.4);
          var g = gSRGB <= .03928 ? gSRGB / 12.92 : Math.pow((gSRGB + .055) / 1.055, 2.4);
          var b = bSRGB <= .03928 ? bSRGB / 12.92 : Math.pow((bSRGB + .055) / 1.055, 2.4);
          return .2126 * r + .7152 * g + .0722 * b;
        };
      };
      color.flattenColors = function(fgColor, bgColor) {
        var alpha = fgColor.alpha;
        var r = (1 - alpha) * bgColor.red + alpha * fgColor.red;
        var g = (1 - alpha) * bgColor.green + alpha * fgColor.green;
        var b = (1 - alpha) * bgColor.blue + alpha * fgColor.blue;
        var a = fgColor.alpha + bgColor.alpha * (1 - fgColor.alpha);
        return new color.Color(r, g, b, a);
      };
      color.getContrast = function(bgColor, fgColor) {
        if (!fgColor || !bgColor) {
          return null;
        }
        if (fgColor.alpha < 1) {
          fgColor = color.flattenColors(fgColor, bgColor);
        }
        var bL = bgColor.getRelativeLuminance();
        var fL = fgColor.getRelativeLuminance();
        return (Math.max(fL, bL) + .05) / (Math.min(fL, bL) + .05);
      };
      color.hasValidContrastRatio = function(bg, fg, fontSize, isBold) {
        var contrast = color.getContrast(bg, fg);
        var isSmallFont = isBold && Math.ceil(fontSize * 72) / 96 < 14 || !isBold && Math.ceil(fontSize * 72) / 96 < 18;
        var expectedContrastRatio = isSmallFont ? 4.5 : 3;
        return {
          isValid: contrast > expectedContrastRatio,
          contrastRatio: contrast,
          expectedContrastRatio: expectedContrastRatio
        };
      };
      color.elementHasImage = function elementHasImage(elm, style) {
        var graphicNodes = [ 'IMG', 'CANVAS', 'OBJECT', 'IFRAME', 'VIDEO', 'SVG' ];
        var nodeName = elm.nodeName.toUpperCase();
        if (graphicNodes.includes(nodeName)) {
          axe.commons.color.incompleteData.set('bgColor', 'imgNode');
          return true;
        }
        style = style || window.getComputedStyle(elm);
        var bgImageStyle = style.getPropertyValue('background-image');
        var hasBgImage = bgImageStyle !== 'none';
        if (hasBgImage) {
          var hasGradient = /gradient/.test(bgImageStyle);
          axe.commons.color.incompleteData.set('bgColor', hasGradient ? 'bgGradient' : 'bgImage');
        }
        return hasBgImage;
      };
      function _getFonts(style) {
        return style.getPropertyValue('font-family').split(/[,;]/g).map(function(font) {
          return font.trim().toLowerCase();
        });
      }
      function elementIsDistinct(node, ancestorNode) {
        var nodeStyle = window.getComputedStyle(node);
        if (nodeStyle.getPropertyValue('background-image') !== 'none') {
          return true;
        }
        var hasBorder = [ 'border-bottom', 'border-top', 'outline' ].reduce(function(result, edge) {
          var borderClr = new color.Color();
          borderClr.parseRgbString(nodeStyle.getPropertyValue(edge + '-color'));
          return result || nodeStyle.getPropertyValue(edge + '-style') !== 'none' && parseFloat(nodeStyle.getPropertyValue(edge + '-width')) > 0 && borderClr.alpha !== 0;
        }, false);
        if (hasBorder) {
          return true;
        }
        var parentStyle = window.getComputedStyle(ancestorNode);
        if (_getFonts(nodeStyle)[0] !== _getFonts(parentStyle)[0]) {
          return true;
        }
        var hasStyle = [ 'text-decoration-line', 'text-decoration-style', 'font-weight', 'font-style', 'font-size' ].reduce(function(result, cssProp) {
          return result || nodeStyle.getPropertyValue(cssProp) !== parentStyle.getPropertyValue(cssProp);
        }, false);
        var tDec = nodeStyle.getPropertyValue('text-decoration');
        if (tDec.split(' ').length < 3) {
          hasStyle = hasStyle || tDec !== parentStyle.getPropertyValue('text-decoration');
        }
        return hasStyle;
      }
      color.elementIsDistinct = elementIsDistinct;
      color.getBackgroundColor = function getBackgroundColor(elm) {
        var bgElms = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : [];
        var bgColors = [];
        var elmStack = color.getBackgroundStack(elm);
        (elmStack || []).some(function(bgElm) {
          var bgElmStyle = window.getComputedStyle(bgElm);
          var bgColor = color.getOwnBackgroundColor(bgElmStyle);
          if (elmPartiallyObscured(elm, bgElm, bgColor) || color.elementHasImage(bgElm, bgElmStyle)) {
            bgColors = null;
            bgElms.push(bgElm);
            return true;
          }
          if (bgColor.alpha !== 0) {
            bgElms.push(bgElm);
            bgColors.push(bgColor);
            return bgColor.alpha === 1;
          } else {
            return false;
          }
        });
        if (bgColors !== null && elmStack !== null) {
          bgColors.push(new color.Color(255, 255, 255, 1));
          var colors = bgColors.reduce(color.flattenColors);
          return colors;
        }
        return null;
      };
      color.getBackgroundStack = function getBackgroundStack(elm) {
        var elmStack = color.filteredRectStack(elm);
        if (elmStack === null) {
          return null;
        }
        elmStack = dom.reduceToElementsBelowFloating(elmStack, elm);
        elmStack = sortPageBackground(elmStack);
        var elmIndex = elmStack.indexOf(elm);
        if (calculateObscuringElement(elmIndex, elmStack, elm)) {
          axe.commons.color.incompleteData.set('bgColor', 'bgOverlap');
          return null;
        }
        return elmIndex !== -1 ? elmStack : null;
      };
      color.filteredRectStack = function filteredRectStack(elm) {
        var rectStack = color.getRectStack(elm);
        if (rectStack && rectStack.length === 1) {
          return rectStack[0];
        }
        if (rectStack && rectStack.length > 1) {
          var boundingStack = rectStack.shift();
          var isSame;
          rectStack.forEach(function(rectList, index) {
            if (index === 0) {
              return;
            }
            var rectA = rectStack[index - 1], rectB = rectStack[index];
            isSame = rectA.every(function(element, elementIndex) {
              return element === rectB[elementIndex];
            }) || boundingStack.includes(elm);
          });
          if (!isSame) {
            axe.commons.color.incompleteData.set('bgColor', 'elmPartiallyObscuring');
            return null;
          }
          return rectStack[0];
        }
        axe.commons.color.incompleteData.set('bgColor', 'outsideViewport');
        return null;
      };
      color.getRectStack = function(elm) {
        var boundingStack = axe.commons.dom.getElementStack(elm);
        var filteredArr = axe.commons.dom.getTextElementStack(elm);
        if (!filteredArr || filteredArr.length <= 1) {
          return [ boundingStack ];
        }
        if (filteredArr.some(function(stack) {
          return stack === undefined;
        })) {
          return null;
        }
        filteredArr.splice(0, 0, boundingStack);
        return filteredArr;
      };
      function sortPageBackground(elmStack) {
        var bodyIndex = elmStack.indexOf(document.body);
        var bgNodes = elmStack;
        var sortBodyElement = bodyIndex > 1 || bodyIndex === -1;
        if (sortBodyElement && !color.elementHasImage(document.documentElement) && color.getOwnBackgroundColor(window.getComputedStyle(document.documentElement)).alpha === 0) {
          if (bodyIndex > 1) {
            bgNodes.splice(bodyIndex, 1);
          }
          bgNodes.splice(elmStack.indexOf(document.documentElement), 1);
          bgNodes.push(document.body);
        }
        return bgNodes;
      }
      function elmPartiallyObscured(elm, bgElm, bgColor) {
        var obscured = elm !== bgElm && !dom.visuallyContains(elm, bgElm) && bgColor.alpha !== 0;
        if (obscured) {
          axe.commons.color.incompleteData.set('bgColor', 'elmPartiallyObscured');
        }
        return obscured;
      }
      function calculateObscuringElement(elmIndex, elmStack, originalElm) {
        if (elmIndex > 0) {
          for (var i = elmIndex - 1; i >= 0; i--) {
            var bgElm = elmStack[i];
            if (contentOverlapping(originalElm, bgElm)) {
              return true;
            } else {
              elmStack.splice(i, 1);
            }
          }
        }
        return false;
      }
      function contentOverlapping(targetElement, bgNode) {
        var targetRect = targetElement.getClientRects()[0];
        var obscuringElements = dom.shadowElementsFromPoint(targetRect.left, targetRect.top);
        if (obscuringElements) {
          for (var i = 0; i < obscuringElements.length; i++) {
            if (obscuringElements[i] !== targetElement && obscuringElements[i] === bgNode) {
              return true;
            }
          }
        }
        return false;
      }
      dom.isOpaque = function(node) {
        var style = window.getComputedStyle(node);
        return color.elementHasImage(node, style) || color.getOwnBackgroundColor(style).alpha === 1;
      };
      function getOpacity(node) {
        if (!node) {
          return 1;
        }
        var vNode = axe.utils.getNodeFromTree(node);
        if (vNode && vNode._opacity !== undefined && vNode._opacity !== null) {
          return vNode._opacity;
        }
        var nodeStyle = window.getComputedStyle(node);
        var opacity = nodeStyle.getPropertyValue('opacity');
        var finalOpacity = opacity * getOpacity(node.parentElement);
        if (vNode) {
          vNode._opacity = finalOpacity;
        }
        return finalOpacity;
      }
      color.getForegroundColor = function(node, noScroll, bgColor) {
        var nodeStyle = window.getComputedStyle(node);
        var fgColor = new color.Color();
        fgColor.parseRgbString(nodeStyle.getPropertyValue('color'));
        var opacity = getOpacity(node);
        fgColor.alpha = fgColor.alpha * opacity;
        if (fgColor.alpha === 1) {
          return fgColor;
        }
        if (!bgColor) {
          bgColor = color.getBackgroundColor(node, [], noScroll);
        }
        if (bgColor === null) {
          var reason = axe.commons.color.incompleteData.get('bgColor');
          axe.commons.color.incompleteData.set('fgColor', reason);
          return null;
        }
        return color.flattenColors(fgColor, bgColor);
      };
      color.getOwnBackgroundColor = function getOwnBackgroundColor(elmStyle) {
        var bgColor = new color.Color();
        bgColor.parseRgbString(elmStyle.getPropertyValue('background-color'));
        if (bgColor.alpha !== 0) {
          var opacity = elmStyle.getPropertyValue('opacity');
          bgColor.alpha = bgColor.alpha * opacity;
        }
        return bgColor;
      };
      color.incompleteData = function() {
        var data = {};
        return {
          set: function set(key, reason) {
            if (typeof key !== 'string') {
              throw new Error('Incomplete data: key must be a string');
            }
            if (reason) {
              data[key] = reason;
            }
            return data[key];
          },
          get: function get(key) {
            return data[key];
          },
          clear: function clear() {
            data = {};
          }
        };
      }();
      dom.reduceToElementsBelowFloating = function(elements, targetNode) {
        var floatingPositions = [ 'fixed', 'sticky' ], finalElements = [], targetFound = false, index, currentNode, style;
        for (index = 0; index < elements.length; ++index) {
          currentNode = elements[index];
          if (currentNode === targetNode) {
            targetFound = true;
          }
          style = window.getComputedStyle(currentNode);
          if (!targetFound && floatingPositions.indexOf(style.position) !== -1) {
            finalElements = [];
            continue;
          }
          finalElements.push(currentNode);
        }
        return finalElements;
      };
      dom.findElmsInContext = function(_ref39) {
        var context = _ref39.context, value = _ref39.value, attr = _ref39.attr, _ref39$elm = _ref39.elm, elm = _ref39$elm === void 0 ? '' : _ref39$elm;
        var root;
        var escapedValue = axe.utils.escapeSelector(value);
        if (context.nodeType === 9 || context.nodeType === 11) {
          root = context;
        } else {
          root = dom.getRootNode(context);
        }
        return Array.from(root.querySelectorAll(elm + '[' + attr + '=' + escapedValue + ']'));
      };
      dom.findUp = function(element, target) {
        return dom.findUpVirtual(axe.utils.getNodeFromTree(element), target);
      };
      dom.findUpVirtual = function(element, target) {
        var parent;
        parent = element.actualNode;
        if (!element.shadowId && typeof element.actualNode.closest === 'function') {
          var match = element.actualNode.closest(target);
          if (match) {
            return match;
          }
          return null;
        }
        do {
          parent = parent.assignedSlot ? parent.assignedSlot : parent.parentNode;
          if (parent && parent.nodeType === 11) {
            parent = parent.host;
          }
        } while (parent && !axe.utils.matchesSelector(parent, target) && parent !== document.documentElement);
        if (!parent) {
          return null;
        }
        if (!axe.utils.matchesSelector(parent, target)) {
          return null;
        }
        return parent;
      };
      dom.getComposedParent = function getComposedParent(element) {
        if (element.assignedSlot) {
          return getComposedParent(element.assignedSlot);
        } else if (element.parentNode) {
          var parentNode = element.parentNode;
          if (parentNode.nodeType === 1) {
            return parentNode;
          } else if (parentNode.host) {
            return parentNode.host;
          }
        }
        return null;
      };
      dom.getElementByReference = function(node, attr) {
        var fragment = node.getAttribute(attr);
        if (!fragment) {
          return null;
        }
        if (fragment.charAt(0) === '#') {
          fragment = decodeURIComponent(fragment.substring(1));
        } else if (fragment.substr(0, 2) === '/#') {
          fragment = decodeURIComponent(fragment.substring(2));
        }
        var candidate = document.getElementById(fragment);
        if (candidate) {
          return candidate;
        }
        candidate = document.getElementsByName(fragment);
        if (candidate.length) {
          return candidate[0];
        }
        return null;
      };
      dom.getElementCoordinates = function(element) {
        'use strict';
        var scrollOffset = dom.getScrollOffset(document), xOffset = scrollOffset.left, yOffset = scrollOffset.top, coords = element.getBoundingClientRect();
        return {
          top: coords.top + yOffset,
          right: coords.right + xOffset,
          bottom: coords.bottom + yOffset,
          left: coords.left + xOffset,
          width: coords.right - coords.left,
          height: coords.bottom - coords.top
        };
      };
      var gridSize = 200;
      function isStackingContext(vNode, parentVNode) {
        var position = vNode.getComputedStylePropertyValue('position');
        var zIndex = vNode.getComputedStylePropertyValue('z-index');
        if (position === 'fixed' || position === 'sticky') {
          return true;
        }
        if (zIndex !== 'auto' && position !== 'static') {
          return true;
        }
        if (vNode.getComputedStylePropertyValue('opacity') !== '1') {
          return true;
        }
        var transform = vNode.getComputedStylePropertyValue('-webkit-transform') || vNode.getComputedStylePropertyValue('-ms-transform') || vNode.getComputedStylePropertyValue('transform') || 'none';
        if (transform !== 'none') {
          return true;
        }
        var mixBlendMode = vNode.getComputedStylePropertyValue('mix-blend-mode');
        if (mixBlendMode && mixBlendMode !== 'normal') {
          return true;
        }
        var filter = vNode.getComputedStylePropertyValue('filter');
        if (filter && filter !== 'none') {
          return true;
        }
        var perspective = vNode.getComputedStylePropertyValue('perspective');
        if (perspective && perspective !== 'none') {
          return true;
        }
        var clipPath = vNode.getComputedStylePropertyValue('clip-path');
        if (clipPath && clipPath !== 'none') {
          return true;
        }
        var mask = vNode.getComputedStylePropertyValue('-webkit-mask') || vNode.getComputedStylePropertyValue('mask') || 'none';
        if (mask !== 'none') {
          return true;
        }
        var maskImage = vNode.getComputedStylePropertyValue('-webkit-mask-image') || vNode.getComputedStylePropertyValue('mask-image') || 'none';
        if (maskImage !== 'none') {
          return true;
        }
        var maskBorder = vNode.getComputedStylePropertyValue('-webkit-mask-border') || vNode.getComputedStylePropertyValue('mask-border') || 'none';
        if (maskBorder !== 'none') {
          return true;
        }
        if (vNode.getComputedStylePropertyValue('isolation') === 'isolate') {
          return true;
        }
        var willChange = vNode.getComputedStylePropertyValue('will-change');
        if (willChange === 'transform' || willChange === 'opacity') {
          return true;
        }
        if (vNode.getComputedStylePropertyValue('-webkit-overflow-scrolling') === 'touch') {
          return true;
        }
        var contain = vNode.getComputedStylePropertyValue('contain');
        if ([ 'layout', 'paint', 'strict', 'content' ].includes(contain)) {
          return true;
        }
        if (zIndex !== 'auto' && parentVNode) {
          var parentDsiplay = parentVNode.getComputedStylePropertyValue('display');
          if ([ 'flex', 'inline-flex', 'inline flex', 'grid', 'inline-grid', 'inline grid' ].includes(parentDsiplay)) {
            return true;
          }
        }
        return false;
      }
      function isFloated(vNode) {
        if (!vNode) {
          return false;
        }
        if (vNode._isFloated !== undefined) {
          return vNode._isFloated;
        }
        var floatStyle = vNode.getComputedStylePropertyValue('float');
        if (floatStyle !== 'none') {
          vNode._isFloated = true;
          return true;
        }
        var floated = isFloated(vNode.parent);
        vNode._isFloated = floated;
        return floated;
      }
      function getPositionOrder(vNode) {
        if (vNode.getComputedStylePropertyValue('position') === 'static') {
          if (vNode.getComputedStylePropertyValue('display').indexOf('inline') !== -1) {
            return 2;
          }
          if (isFloated(vNode)) {
            return 1;
          }
          return 0;
        }
        return 3;
      }
      function visuallySort(a, b) {
        for (var i = 0; i < a._stackingOrder.length; i++) {
          if (typeof b._stackingOrder[i] === 'undefined') {
            return -1;
          }
          if (b._stackingOrder[i] > a._stackingOrder[i]) {
            return 1;
          }
          if (b._stackingOrder[i] < a._stackingOrder[i]) {
            return -1;
          }
        }
        var aNode = a.actualNode;
        var bNode = b.actualNode;
        if (aNode.getRootNode && aNode.getRootNode() !== bNode.getRootNode()) {
          var boundaries = [];
          while (aNode) {
            boundaries.push({
              root: aNode.getRootNode(),
              node: aNode
            });
            aNode = aNode.getRootNode().host;
          }
          while (bNode && !boundaries.find(function(boundary) {
            return boundary.root === bNode.getRootNode();
          })) {
            bNode = bNode.getRootNode().host;
          }
          aNode = boundaries.find(function(boundary) {
            return boundary.root === bNode.getRootNode();
          }).node;
          if (aNode === bNode) {
            return a.actualNode.getRootNode() !== aNode.getRootNode() ? -1 : 1;
          }
        }
        var _window$Node = window.Node, DOCUMENT_POSITION_FOLLOWING = _window$Node.DOCUMENT_POSITION_FOLLOWING, DOCUMENT_POSITION_CONTAINS = _window$Node.DOCUMENT_POSITION_CONTAINS, DOCUMENT_POSITION_CONTAINED_BY = _window$Node.DOCUMENT_POSITION_CONTAINED_BY;
        var docPosition = aNode.compareDocumentPosition(bNode);
        var DOMOrder = docPosition & DOCUMENT_POSITION_FOLLOWING ? 1 : -1;
        var isDescendant = docPosition & DOCUMENT_POSITION_CONTAINS || docPosition & DOCUMENT_POSITION_CONTAINED_BY;
        var aPosition = getPositionOrder(a);
        var bPosition = getPositionOrder(b);
        if (aPosition === bPosition || isDescendant) {
          return DOMOrder;
        }
        return bPosition - aPosition;
      }
      function getStackingOrder(vNode, parentVNode) {
        var stackingOrder = parentVNode._stackingOrder.slice();
        var zIndex = vNode.getComputedStylePropertyValue('z-index');
        if (zIndex !== 'auto') {
          stackingOrder[stackingOrder.length - 1] = parseInt(zIndex);
        }
        if (isStackingContext(vNode, parentVNode)) {
          stackingOrder.push(0);
        }
        return stackingOrder;
      }
      function findScrollRegionParent(vNode, parentVNode) {
        var scrollRegionParent = null;
        var checkedNodes = [ vNode ];
        while (parentVNode) {
          if (parentVNode._scrollRegionParent) {
            scrollRegionParent = parentVNode._scrollRegionParent;
            break;
          }
          if (axe.utils.getScroll(parentVNode.actualNode)) {
            scrollRegionParent = parentVNode;
            break;
          }
          checkedNodes.push(parentVNode);
          parentVNode = axe.utils.getNodeFromTree(parentVNode.actualNode.parentElement || parentVNode.actualNode.parentNode);
        }
        checkedNodes.forEach(function(vNode) {
          return vNode._scrollRegionParent = scrollRegionParent;
        });
        return scrollRegionParent;
      }
      function addNodeToGrid(grid, vNode) {
        vNode._grid = grid;
        vNode.clientRects.forEach(function(rect) {
          var x = rect.left;
          var y = rect.top;
          var startRow = y / gridSize | 0;
          var startCol = x / gridSize | 0;
          var endRow = (y + rect.height) / gridSize | 0;
          var endCol = (x + rect.width) / gridSize | 0;
          for (var row = startRow; row <= endRow; row++) {
            grid.cells[row] = grid.cells[row] || [];
            for (var col = startCol; col <= endCol; col++) {
              grid.cells[row][col] = grid.cells[row][col] || [];
              if (!grid.cells[row][col].includes(vNode)) {
                grid.cells[row][col].push(vNode);
              }
            }
          }
        });
      }
      function createGrid() {
        var root = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : document.body;
        var rootGrid = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {
          container: null,
          cells: []
        };
        var parentVNode = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : null;
        if (!parentVNode) {
          var vNode = axe.utils.getNodeFromTree(document.documentElement);
          if (!vNode) {
            vNode = new VirtualNode(document.documentElement);
          }
          vNode._stackingOrder = [ 0 ];
          addNodeToGrid(rootGrid, vNode);
          if (axe.utils.getScroll(vNode.actualNode)) {
            var subGrid = {
              container: vNode,
              cells: []
            };
            vNode._subGrid = subGrid;
          }
        }
        var treeWalker = document.createTreeWalker(root, window.NodeFilter.SHOW_ELEMENT, null, false);
        var node = parentVNode ? treeWalker.nextNode() : treeWalker.currentNode;
        while (node) {
          var _vNode = axe.utils.getNodeFromTree(node);
          if (node.parentElement) {
            parentVNode = axe.utils.getNodeFromTree(node.parentElement);
          } else if (node.parentNode && axe.utils.getNodeFromTree(node.parentNode)) {
            parentVNode = axe.utils.getNodeFromTree(node.parentNode);
          }
          if (!_vNode) {
            _vNode = new VirtualNode(node, parentVNode);
          }
          _vNode._stackingOrder = getStackingOrder(_vNode, parentVNode);
          var scrollRegionParent = findScrollRegionParent(_vNode, parentVNode);
          var grid = scrollRegionParent ? scrollRegionParent._subGrid : rootGrid;
          if (axe.utils.getScroll(_vNode.actualNode)) {
            var _subGrid = {
              container: _vNode,
              cells: []
            };
            _vNode._subGrid = _subGrid;
          }
          var rect = _vNode.boundingClientRect;
          if (rect.width !== 0 && rect.height !== 0 && dom.isVisible(node)) {
            addNodeToGrid(grid, _vNode);
          }
          if (axe.utils.isShadowRoot(node)) {
            createGrid(node.shadowRoot, grid, _vNode);
          }
          node = treeWalker.nextNode();
        }
      }
      function getRectStack(grid, rect) {
        var recursed = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : false;
        var x = rect.left + rect.width / 2;
        var y = rect.top + rect.height / 2;
        var row = y / gridSize | 0;
        var col = x / gridSize | 0;
        var stack = grid.cells[row][col].filter(function(gridCellNode) {
          return gridCellNode.clientRects.find(function(clientRect) {
            var rectX = clientRect.left;
            var rectY = clientRect.top;
            return x <= rectX + clientRect.width && x >= rectX && y <= rectY + clientRect.height && y >= rectY;
          });
        });
        var gridContainer = grid.container;
        if (gridContainer) {
          stack = getRectStack(gridContainer._grid, gridContainer.boundingClientRect, true).concat(stack);
        }
        if (!recursed) {
          stack = stack.sort(visuallySort).map(function(vNode) {
            return vNode.actualNode;
          }).concat(document.documentElement).filter(function(node, index, array) {
            return array.indexOf(node) === index;
          });
        }
        return stack;
      }
      dom.getElementStack = function(node) {
        if (!axe._cache.get('gridCreated')) {
          createGrid();
          axe._cache.set('gridCreated', true);
        }
        var vNode = axe.utils.getNodeFromTree(node);
        var grid = vNode._grid;
        if (!grid) {
          return [];
        }
        return getRectStack(grid, vNode.boundingClientRect);
      };
      dom.getTextElementStack = function(node) {
        if (!axe._cache.get('gridCreated')) {
          createGrid();
          axe._cache.set('gridCreated', true);
        }
        var vNode = axe.utils.getNodeFromTree(node);
        var grid = vNode._grid;
        if (!grid) {
          return [];
        }
        var clientRects = [];
        Array.from(node.childNodes).forEach(function(elm) {
          if (elm.nodeType === 3 && axe.commons.text.sanitize(elm.textContent) !== '') {
            var range = document.createRange();
            range.selectNodeContents(elm);
            var rects = range.getClientRects();
            for (var i = 0; i < rects.length; i++) {
              var rect = rects[i];
              if (rect.width >= 1 && rect.height >= 1) {
                clientRects.push(rect);
              }
            }
          }
        });
        return clientRects.map(function(rect) {
          return getRectStack(grid, rect);
        });
      };
      dom.getRootNode = axe.utils.getRootNode;
      dom.getScrollOffset = function(element) {
        'use strict';
        if (!element.nodeType && element.document) {
          element = element.document;
        }
        if (element.nodeType === 9) {
          var docElement = element.documentElement, body = element.body;
          return {
            left: docElement && docElement.scrollLeft || body && body.scrollLeft || 0,
            top: docElement && docElement.scrollTop || body && body.scrollTop || 0
          };
        }
        return {
          left: element.scrollLeft,
          top: element.scrollTop
        };
      };
      dom.getTabbableElements = function getTabbableElements(virtualNode) {
        var nodeAndDescendents = axe.utils.querySelectorAll(virtualNode, '*');
        var tabbableElements = nodeAndDescendents.filter(function(vNode) {
          var isFocusable = vNode.isFocusable;
          var tabIndex = vNode.actualNode.getAttribute('tabindex');
          tabIndex = tabIndex && !isNaN(parseInt(tabIndex, 10)) ? parseInt(tabIndex) : null;
          return tabIndex ? isFocusable && tabIndex >= 0 : isFocusable;
        });
        return tabbableElements;
      };
      dom.getViewportSize = function(win) {
        'use strict';
        var body, doc = win.document, docElement = doc.documentElement;
        if (win.innerWidth) {
          return {
            width: win.innerWidth,
            height: win.innerHeight
          };
        }
        if (docElement) {
          return {
            width: docElement.clientWidth,
            height: docElement.clientHeight
          };
        }
        body = doc.body;
        return {
          width: body.clientWidth,
          height: body.clientHeight
        };
      };
      var hiddenTextElms = [ 'HEAD', 'TITLE', 'TEMPLATE', 'SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'VIDEO', 'AUDIO', 'NOSCRIPT' ];
      function hasChildTextNodes(elm) {
        if (!hiddenTextElms.includes(elm.actualNode.nodeName.toUpperCase())) {
          return elm.children.some(function(_ref40) {
            var actualNode = _ref40.actualNode;
            return actualNode.nodeType === 3 && actualNode.nodeValue.trim();
          });
        }
      }
      dom.hasContentVirtual = function(elm, noRecursion, ignoreAria) {
        return hasChildTextNodes(elm) || dom.isVisualContent(elm.actualNode) || !ignoreAria && !!aria.labelVirtual(elm) || !noRecursion && elm.children.some(function(child) {
          return child.actualNode.nodeType === 1 && dom.hasContentVirtual(child);
        });
      };
      dom.hasContent = function hasContent(elm, noRecursion, ignoreAria) {
        elm = axe.utils.getNodeFromTree(elm);
        return dom.hasContentVirtual(elm, noRecursion, ignoreAria);
      };
      dom.idrefs = function(node, attr) {
        'use strict';
        var index, length, doc = dom.getRootNode(node), result = [], idrefs = node.getAttribute(attr);
        if (idrefs) {
          idrefs = axe.utils.tokenList(idrefs);
          for (index = 0, length = idrefs.length; index < length; index++) {
            result.push(doc.getElementById(idrefs[index]));
          }
        }
        return result;
      };
      function focusDisabled(el) {
        return el.disabled || el.nodeName.toUpperCase() !== 'AREA' && dom.isHiddenWithCSS(el);
      }
      dom.isFocusable = function(el) {
        'use strict';
        if (focusDisabled(el)) {
          return false;
        } else if (dom.isNativelyFocusable(el)) {
          return true;
        }
        var tabindex = el.getAttribute('tabindex');
        if (tabindex && !isNaN(parseInt(tabindex, 10))) {
          return true;
        }
        return false;
      };
      dom.isNativelyFocusable = function(el) {
        'use strict';
        if (!el || focusDisabled(el)) {
          return false;
        }
        switch (el.nodeName.toUpperCase()) {
         case 'A':
         case 'AREA':
          if (el.href) {
            return true;
          }
          break;

         case 'INPUT':
          return el.type !== 'hidden';

         case 'TEXTAREA':
         case 'SELECT':
         case 'SUMMARY':
         case 'BUTTON':
          return true;

         case 'DETAILS':
          return !el.querySelector('summary');
        }
        return false;
      };
      dom.insertedIntoFocusOrder = function(el) {
        var tabIndex = parseInt(el.getAttribute('tabindex'), 10);
        return tabIndex > -1 && dom.isFocusable(el) && !dom.isNativelyFocusable(el);
      };
      dom.isHiddenWithCSS = function isHiddenWithCSS(el, descendentVisibilityValue) {
        var vNode = axe.utils.getNodeFromTree(el);
        if (!vNode) {
          return _isHiddenWithCSS(el, descendentVisibilityValue);
        }
        if (vNode._isHiddenWithCSS === void 0) {
          vNode._isHiddenWithCSS = _isHiddenWithCSS(el, descendentVisibilityValue);
        }
        return vNode._isHiddenWithCSS;
      };
      function _isHiddenWithCSS(el, descendentVisibilityValue) {
        if (el.nodeType === 9) {
          return false;
        }
        if (el.nodeType === 11) {
          el = el.host;
        }
        if ([ 'STYLE', 'SCRIPT' ].includes(el.nodeName.toUpperCase())) {
          return false;
        }
        var style = window.getComputedStyle(el, null);
        if (!style) {
          throw new Error('Style does not exist for the given element.');
        }
        var displayValue = style.getPropertyValue('display');
        if (displayValue === 'none') {
          return true;
        }
        var HIDDEN_VISIBILITY_VALUES = [ 'hidden', 'collapse' ];
        var visibilityValue = style.getPropertyValue('visibility');
        if (HIDDEN_VISIBILITY_VALUES.includes(visibilityValue) && !descendentVisibilityValue) {
          return true;
        }
        if (HIDDEN_VISIBILITY_VALUES.includes(visibilityValue) && descendentVisibilityValue && HIDDEN_VISIBILITY_VALUES.includes(descendentVisibilityValue)) {
          return true;
        }
        var parent = dom.getComposedParent(el);
        if (parent && !HIDDEN_VISIBILITY_VALUES.includes(visibilityValue)) {
          return dom.isHiddenWithCSS(parent, visibilityValue);
        }
        return false;
      }
      dom.isHTML5 = function(doc) {
        var node = doc.doctype;
        if (node === null) {
          return false;
        }
        return node.name === 'html' && !node.publicId && !node.systemId;
      };
      function walkDomNode(node, functor) {
        if (functor(node.actualNode) !== false) {
          node.children.forEach(function(child) {
            return walkDomNode(child, functor);
          });
        }
      }
      var blockLike = [ 'block', 'list-item', 'table', 'flex', 'grid', 'inline-block' ];
      function isBlock(elm) {
        var display = window.getComputedStyle(elm).getPropertyValue('display');
        return blockLike.includes(display) || display.substr(0, 6) === 'table-';
      }
      function getBlockParent(node) {
        var parentBlock = dom.getComposedParent(node);
        while (parentBlock && !isBlock(parentBlock)) {
          parentBlock = dom.getComposedParent(parentBlock);
        }
        return axe.utils.getNodeFromTree(parentBlock);
      }
      dom.isInTextBlock = function isInTextBlock(node) {
        if (isBlock(node)) {
          return false;
        }
        var virtualParent = getBlockParent(node);
        var parentText = '';
        var linkText = '';
        var inBrBlock = 0;
        walkDomNode(virtualParent, function(currNode) {
          if (inBrBlock === 2) {
            return false;
          }
          if (currNode.nodeType === 3) {
            parentText += currNode.nodeValue;
          }
          if (currNode.nodeType !== 1) {
            return;
          }
          var nodeName = (currNode.nodeName || '').toUpperCase();
          if ([ 'BR', 'HR' ].includes(nodeName)) {
            if (inBrBlock === 0) {
              parentText = '';
              linkText = '';
            } else {
              inBrBlock = 2;
            }
          } else if (currNode.style.display === 'none' || currNode.style.overflow === 'hidden' || ![ '', null, 'none' ].includes(currNode.style['float']) || ![ '', null, 'relative' ].includes(currNode.style.position)) {
            return false;
          } else if (nodeName === 'A' && currNode.href || (currNode.getAttribute('role') || '').toLowerCase() === 'link') {
            if (currNode === node) {
              inBrBlock = 1;
            }
            linkText += currNode.textContent;
            return false;
          }
        });
        parentText = axe.commons.text.sanitize(parentText);
        linkText = axe.commons.text.sanitize(linkText);
        return parentText.length > linkText.length;
      };
      dom.isModalOpen = function isModalOpen(options) {
        options = options || {};
        var modalPercent = options.modalPercent || .75;
        if (axe._cache.get('isModalOpen')) {
          return axe._cache.get('isModalOpen');
        }
        var definiteModals = axe.utils.querySelectorAllFilter(axe._tree[0], 'dialog, [role=dialog], [aria-modal=true]', function(vNode) {
          return dom.isVisible(vNode.actualNode);
        });
        if (definiteModals.length) {
          axe._cache.set('isModalOpen', true);
          return true;
        }
        var viewport = dom.getViewportSize(window);
        var percentWidth = viewport.width * modalPercent;
        var percentHeight = viewport.height * modalPercent;
        var x = (viewport.width - percentWidth) / 2;
        var y = (viewport.height - percentHeight) / 2;
        var points = [ {
          x: x,
          y: y
        }, {
          x: viewport.width - x,
          y: y
        }, {
          x: viewport.width / 2,
          y: viewport.height / 2
        }, {
          x: x,
          y: viewport.height - y
        }, {
          x: viewport.width - x,
          y: viewport.height - y
        } ];
        var stacks = points.map(function(point) {
          return Array.from(document.elementsFromPoint(point.x, point.y));
        });
        var _loop3 = function _loop3(i) {
          var modalElement = stacks[i].find(function(elm) {
            var style = window.getComputedStyle(elm);
            return parseInt(style.width, 10) >= percentWidth && parseInt(style.height, 10) >= percentHeight && style.getPropertyValue('pointer-events') !== 'none' && (style.position === 'absolute' || style.position === 'fixed');
          });
          if (modalElement && stacks.every(function(stack) {
            return stack.includes(modalElement);
          })) {
            axe._cache.set('isModalOpen', true);
            return {
              v: true
            };
          }
        };
        for (var i = 0; i < stacks.length; i++) {
          var _ret3 = _loop3(i);
          if (_typeof(_ret3) === 'object') {
            return _ret3.v;
          }
        }
        axe._cache.set('isModalOpen', undefined);
        return undefined;
      };
      dom.isNode = function(element) {
        'use strict';
        return element instanceof Node;
      };
      function noParentScrolled(element, offset) {
        element = dom.getComposedParent(element);
        while (element && element.nodeName.toLowerCase() !== 'html') {
          if (element.scrollTop) {
            offset += element.scrollTop;
            if (offset >= 0) {
              return false;
            }
          }
          element = dom.getComposedParent(element);
        }
        return true;
      }
      dom.isOffscreen = function(element) {
        var leftBoundary;
        var docElement = document.documentElement;
        var styl = window.getComputedStyle(element);
        var dir = window.getComputedStyle(document.body || docElement).getPropertyValue('direction');
        var coords = dom.getElementCoordinates(element);
        if (coords.bottom < 0 && (noParentScrolled(element, coords.bottom) || styl.position === 'absolute')) {
          return true;
        }
        if (coords.left === 0 && coords.right === 0) {
          return false;
        }
        if (dir === 'ltr') {
          if (coords.right <= 0) {
            return true;
          }
        } else {
          leftBoundary = Math.max(docElement.scrollWidth, dom.getViewportSize(window).width);
          if (coords.left >= leftBoundary) {
            return true;
          }
        }
        return false;
      };
      var isInternalLinkRegex = /^\/?#[^/!]/;
      dom.isSkipLink = function(element) {
        if (!isInternalLinkRegex.test(element.getAttribute('href'))) {
          return false;
        }
        var firstPageLink;
        if (typeof axe._cache.get('firstPageLink') !== 'undefined') {
          firstPageLink = axe._cache.get('firstPageLink');
        } else {
          firstPageLink = axe.utils.querySelectorAll(axe._tree, 'a:not([href^="#"]):not([href^="/#"]):not([href^="javascript"])')[0];
          axe._cache.set('firstPageLink', firstPageLink || null);
        }
        if (!firstPageLink) {
          return true;
        }
        return element.compareDocumentPosition(firstPageLink.actualNode) === element.DOCUMENT_POSITION_FOLLOWING;
      };
      var clipRegex = /rect\s*\(([0-9]+)px,?\s*([0-9]+)px,?\s*([0-9]+)px,?\s*([0-9]+)px\s*\)/;
      var clipPathRegex = /(\w+)\((\d+)/;
      function isClipped(style) {
        'use strict';
        var matchesClip = style.getPropertyValue('clip').match(clipRegex);
        var matchesClipPath = style.getPropertyValue('clip-path').match(clipPathRegex);
        if (matchesClip && matchesClip.length === 5) {
          return matchesClip[3] - matchesClip[1] <= 0 && matchesClip[2] - matchesClip[4] <= 0;
        }
        if (matchesClipPath) {
          var type = matchesClipPath[1];
          var value = parseInt(matchesClipPath[2], 10);
          switch (type) {
           case 'inset':
            return value >= 50;

           case 'circle':
            return value === 0;

           default:
          }
        }
        return false;
      }
      function isAreaVisible(el, screenReader, recursed) {
        var mapEl = dom.findUp(el, 'map');
        if (!mapEl) {
          return false;
        }
        var mapElName = mapEl.getAttribute('name');
        if (!mapElName) {
          return false;
        }
        var mapElRootNode = dom.getRootNode(el);
        if (!mapElRootNode || mapElRootNode.nodeType !== 9) {
          return false;
        }
        var refs = axe.utils.querySelectorAll(axe._tree, 'img[usemap="#'.concat(axe.utils.escapeSelector(mapElName), '"]'));
        if (!refs || !refs.length) {
          return false;
        }
        return refs.some(function(_ref41) {
          var actualNode = _ref41.actualNode;
          return dom.isVisible(actualNode, screenReader, recursed);
        });
      }
      dom.isVisible = function(el, screenReader, recursed) {
        'use strict';
        var node = axe.utils.getNodeFromTree(el);
        var cacheName = '_isVisible' + (screenReader ? 'ScreenReader' : '');
        if (el.nodeType === 9) {
          return true;
        }
        if (el.nodeType === 11) {
          el = el.host;
        }
        if (node && typeof node[cacheName] !== 'undefined') {
          return node[cacheName];
        }
        var style = window.getComputedStyle(el, null);
        if (style === null) {
          return false;
        }
        var nodeName = el.nodeName.toUpperCase();
        if (nodeName === 'AREA') {
          return isAreaVisible(el, screenReader, recursed);
        }
        if (style.getPropertyValue('display') === 'none' || [ 'STYLE', 'SCRIPT', 'NOSCRIPT', 'TEMPLATE' ].includes(nodeName)) {
          return false;
        }
        if (screenReader && el.getAttribute('aria-hidden') === 'true') {
          return false;
        }
        if (!screenReader && (isClipped(style) || style.getPropertyValue('opacity') === '0' || axe.utils.getScroll(el) && parseInt(style.getPropertyValue('height')) === 0)) {
          return false;
        }
        if (!recursed && (style.getPropertyValue('visibility') === 'hidden' || !screenReader && axe.commons.dom.isOffscreen(el))) {
          return false;
        }
        var parent = el.assignedSlot ? el.assignedSlot : el.parentNode;
        var isVisible = false;
        if (parent) {
          isVisible = dom.isVisible(parent, screenReader, true);
        }
        if (node) {
          node[cacheName] = isVisible;
        }
        return isVisible;
      };
      var visualRoles = [ 'checkbox', 'img', 'radio', 'range', 'slider', 'spinbutton', 'textbox' ];
      dom.isVisualContent = function(element) {
        var role = element.getAttribute('role');
        if (role) {
          return visualRoles.indexOf(role) !== -1;
        }
        switch (element.nodeName.toUpperCase()) {
         case 'IMG':
         case 'IFRAME':
         case 'OBJECT':
         case 'VIDEO':
         case 'AUDIO':
         case 'CANVAS':
         case 'SVG':
         case 'MATH':
         case 'BUTTON':
         case 'SELECT':
         case 'TEXTAREA':
         case 'KEYGEN':
         case 'PROGRESS':
         case 'METER':
          return true;

         case 'INPUT':
          return element.type !== 'hidden';

         default:
          return false;
        }
      };
      dom.shadowElementsFromPoint = function(nodeX, nodeY) {
        var root = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : document;
        var i = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : 0;
        if (i > 999) {
          throw new Error('Infinite loop detected');
        }
        return Array.from(root.elementsFromPoint(nodeX, nodeY) || []).filter(function(nodes) {
          return dom.getRootNode(nodes) === root;
        }).reduce(function(stack, elm) {
          if (axe.utils.isShadowRoot(elm)) {
            var shadowStack = dom.shadowElementsFromPoint(nodeX, nodeY, elm.shadowRoot, i + 1);
            stack = stack.concat(shadowStack);
            if (stack.length && axe.commons.dom.visuallyContains(stack[0], elm)) {
              stack.push(elm);
            }
          } else {
            stack.push(elm);
          }
          return stack;
        }, []);
      };
      dom.urlPropsFromAttribute = function urlPropsFromAttribute(node, attribute) {
        if (!node.hasAttribute(attribute)) {
          return undefined;
        }
        var nodeName = node.nodeName.toUpperCase();
        var parser = node;
        if (![ 'A', 'AREA' ].includes(nodeName) || node.ownerSVGElement) {
          parser = document.createElement('a');
          parser.href = node.getAttribute(attribute);
        }
        var protocol = [ 'https:', 'ftps:' ].includes(parser.protocol) ? parser.protocol.replace(/s:$/, ':') : parser.protocol;
        var parserPathname = /^\//.test(parser.pathname) ? parser.pathname : '/'.concat(parser.pathname);
        var _getPathnameOrFilenam = getPathnameOrFilename(parserPathname), pathname = _getPathnameOrFilenam.pathname, filename = _getPathnameOrFilenam.filename;
        return {
          protocol: protocol,
          hostname: parser.hostname,
          port: getPort(parser.port),
          pathname: /\/$/.test(pathname) ? pathname : ''.concat(pathname, '/'),
          search: getSearchPairs(parser.search),
          hash: getHashRoute(parser.hash),
          filename: filename
        };
      };
      function getPort(port) {
        var excludePorts = [ '443', '80' ];
        return !excludePorts.includes(port) ? port : '';
      }
      function getPathnameOrFilename(pathname) {
        var filename = pathname.split('/').pop();
        if (!filename || filename.indexOf('.') === -1) {
          return {
            pathname: pathname,
            filename: ''
          };
        }
        return {
          pathname: pathname.replace(filename, ''),
          filename: /index./.test(filename) ? '' : filename
        };
      }
      function getSearchPairs(searchStr) {
        var query = {};
        if (!searchStr || !searchStr.length) {
          return query;
        }
        var pairs = searchStr.substring(1).split('&');
        if (!pairs || !pairs.length) {
          return query;
        }
        for (var index = 0; index < pairs.length; index++) {
          var pair = pairs[index];
          var _pair$split = pair.split('='), _pair$split2 = _slicedToArray(_pair$split, 2), key = _pair$split2[0], _pair$split2$ = _pair$split2[1], value = _pair$split2$ === void 0 ? '' : _pair$split2$;
          query[decodeURIComponent(key)] = decodeURIComponent(value);
        }
        return query;
      }
      function getHashRoute(hash) {
        if (!hash) {
          return '';
        }
        var hashRegex = /#!?\/?/g;
        var hasMatch = hash.match(hashRegex);
        if (!hasMatch) {
          return '';
        }
        var _hasMatch = _slicedToArray(hasMatch, 1), matchedStr = _hasMatch[0];
        if (matchedStr === '#') {
          return '';
        }
        return hash;
      }
      function getScrollAncestor(node) {
        var vNode = axe.utils.getNodeFromTree(node);
        var ancestor = vNode.parent;
        while (ancestor) {
          if (axe.utils.getScroll(ancestor.actualNode)) {
            return ancestor.actualNode;
          }
          ancestor = ancestor.parent;
        }
      }
      function contains(node, parent) {
        var rectBound = node.getBoundingClientRect();
        var margin = .01;
        var rect = {
          top: rectBound.top + margin,
          bottom: rectBound.bottom - margin,
          left: rectBound.left + margin,
          right: rectBound.right - margin
        };
        var parentRect = parent.getBoundingClientRect();
        var parentTop = parentRect.top;
        var parentLeft = parentRect.left;
        var parentScrollArea = {
          top: parentTop - parent.scrollTop,
          bottom: parentTop - parent.scrollTop + parent.scrollHeight,
          left: parentLeft - parent.scrollLeft,
          right: parentLeft - parent.scrollLeft + parent.scrollWidth
        };
        var style = window.getComputedStyle(parent);
        if (style.getPropertyValue('display') === 'inline') {
          return true;
        }
        if (rect.left < parentScrollArea.left && rect.left < parentRect.left || rect.top < parentScrollArea.top && rect.top < parentRect.top || rect.right > parentScrollArea.right && rect.right > parentRect.right || rect.bottom > parentScrollArea.bottom && rect.bottom > parentRect.bottom) {
          return false;
        }
        if (rect.right > parentRect.right || rect.bottom > parentRect.bottom) {
          return style.overflow === 'scroll' || style.overflow === 'auto' || style.overflow === 'hidden' || parent instanceof HTMLBodyElement || parent instanceof HTMLHtmlElement;
        }
        return true;
      }
      dom.visuallyContains = function visuallyContains(node, parent) {
        var parentScrollAncestor = getScrollAncestor(parent);
        do {
          var nextScrollAncestor = getScrollAncestor(node);
          if (nextScrollAncestor === parentScrollAncestor || nextScrollAncestor === parent) {
            return contains(node, parent);
          }
          node = nextScrollAncestor;
        } while (node);
        return false;
      };
      dom.visuallyOverlaps = function(rect, parent) {
        var parentRect = parent.getBoundingClientRect();
        var parentTop = parentRect.top;
        var parentLeft = parentRect.left;
        var parentScrollArea = {
          top: parentTop - parent.scrollTop,
          bottom: parentTop - parent.scrollTop + parent.scrollHeight,
          left: parentLeft - parent.scrollLeft,
          right: parentLeft - parent.scrollLeft + parent.scrollWidth
        };
        if (rect.left > parentScrollArea.right && rect.left > parentRect.right || rect.top > parentScrollArea.bottom && rect.top > parentRect.bottom || rect.right < parentScrollArea.left && rect.right < parentRect.left || rect.bottom < parentScrollArea.top && rect.bottom < parentRect.top) {
          return false;
        }
        var style = window.getComputedStyle(parent);
        if (rect.left > parentRect.right || rect.top > parentRect.bottom) {
          return style.overflow === 'scroll' || style.overflow === 'auto' || parent instanceof HTMLBodyElement || parent instanceof HTMLHtmlElement;
        }
        return true;
      };
      forms.isAriaCombobox = function(node) {
        var role = axe.commons.aria.getRole(node, {
          noImplicit: true
        });
        return role === 'combobox';
      };
      forms.isAriaListbox = function(node) {
        var role = axe.commons.aria.getRole(node, {
          noImplicit: true
        });
        return role === 'listbox';
      };
      var rangeRoles = [ 'progressbar', 'scrollbar', 'slider', 'spinbutton' ];
      forms.isAriaRange = function(node) {
        var role = axe.commons.aria.getRole(node, {
          noImplicit: true
        });
        return rangeRoles.includes(role);
      };
      forms.isAriaTextbox = function(node) {
        var role = axe.commons.aria.getRole(node, {
          noImplicit: true
        });
        return role === 'textbox';
      };
      forms.isNativeSelect = function(node) {
        var nodeName = node.nodeName.toUpperCase();
        return nodeName === 'SELECT';
      };
      var nonTextInputTypes = [ 'button', 'checkbox', 'color', 'file', 'hidden', 'image', 'password', 'radio', 'reset', 'submit' ];
      forms.isNativeTextbox = function(node) {
        var nodeName = node.nodeName.toUpperCase();
        return nodeName === 'TEXTAREA' || nodeName === 'INPUT' && !nonTextInputTypes.includes(node.type);
      };
      matches.attributes = function matchesAttributes(vNode, matcher) {
        if (!(vNode instanceof axe.AbstractVirtualNode)) {
          vNode = axe.utils.getNodeFromTree(vNode);
        }
        return matches.fromFunction(function(attrName) {
          return vNode.attr(attrName);
        }, matcher);
      };
      matches.condition = function(arg, condition) {
        return !!condition(arg);
      };
      var matchers = [ 'nodeName', 'attributes', 'properties', 'condition' ];
      matches.fromDefinition = function matchFromDefinition(vNode, definition) {
        if (!(vNode instanceof axe.AbstractVirtualNode)) {
          vNode = axe.utils.getNodeFromTree(vNode);
        }
        if (Array.isArray(definition)) {
          return definition.some(function(definitionItem) {
            return matches(vNode, definitionItem);
          });
        }
        if (typeof definition === 'string') {
          return axe.utils.matches(vNode, definition);
        }
        return Object.keys(definition).every(function(matcherName) {
          if (!matchers.includes(matcherName)) {
            throw new Error('Unknown matcher type "'.concat(matcherName, '"'));
          }
          var matchMethod = matches[matcherName];
          var matcher = definition[matcherName];
          return matchMethod(vNode, matcher);
        });
      };
      matches.fromFunction = function matchFromFunction(getValue, matcher) {
        var matcherType = _typeof(matcher);
        if (matcherType !== 'object' || Array.isArray(matcher) || matcher instanceof RegExp) {
          throw new Error('Expect matcher to be an object');
        }
        return Object.keys(matcher).every(function(propName) {
          return matches.fromPrimative(getValue(propName), matcher[propName]);
        });
      };
      matches.fromPrimative = function matchFromPrimative(someString, matcher) {
        var matcherType = _typeof(matcher);
        if (Array.isArray(matcher) && typeof someString !== 'undefined') {
          return matcher.includes(someString);
        }
        if (matcherType === 'function') {
          return !!matcher(someString);
        }
        if (matcher instanceof RegExp) {
          return matcher.test(someString);
        }
        return matcher === someString;
      };
      matches.nodeName = function matchNodeName(vNode, matcher) {
        if (!(vNode instanceof axe.AbstractVirtualNode)) {
          vNode = axe.utils.getNodeFromTree(vNode);
        }
        return matches.fromPrimative(vNode.props.nodeName, matcher);
      };
      matches.properties = function matchesProperties(vNode, matcher) {
        if (!(vNode instanceof axe.AbstractVirtualNode)) {
          vNode = axe.utils.getNodeFromTree(vNode);
        }
        return matches.fromFunction(function(propName) {
          return vNode.props[propName];
        }, matcher);
      };
      table.getAllCells = function(tableElm) {
        var rowIndex, cellIndex, rowLength, cellLength;
        var cells = [];
        for (rowIndex = 0, rowLength = tableElm.rows.length; rowIndex < rowLength; rowIndex++) {
          for (cellIndex = 0, cellLength = tableElm.rows[rowIndex].cells.length; cellIndex < cellLength; cellIndex++) {
            cells.push(tableElm.rows[rowIndex].cells[cellIndex]);
          }
        }
        return cells;
      };
      table.getCellPosition = axe.utils.memoize(function(cell, tableGrid) {
        var rowIndex, index;
        if (!tableGrid) {
          tableGrid = table.toGrid(dom.findUp(cell, 'table'));
        }
        for (rowIndex = 0; rowIndex < tableGrid.length; rowIndex++) {
          if (tableGrid[rowIndex]) {
            index = tableGrid[rowIndex].indexOf(cell);
            if (index !== -1) {
              return {
                x: index,
                y: rowIndex
              };
            }
          }
        }
      });
      function traverseForHeaders(headerType, position, tableGrid) {
        var property = headerType === 'row' ? '_rowHeaders' : '_colHeaders';
        var predicate = headerType === 'row' ? table.isRowHeader : table.isColumnHeader;
        var rowEnd = headerType === 'row' ? position.y : 0;
        var colEnd = headerType === 'row' ? 0 : position.x;
        var headers;
        var cells = [];
        for (var row = position.y; row >= rowEnd && !headers; row--) {
          for (var col = position.x; col >= colEnd; col--) {
            var cell = tableGrid[row] ? tableGrid[row][col] : undefined;
            if (!cell) {
              continue;
            }
            var vNode = axe.utils.getNodeFromTree(cell);
            if (vNode[property]) {
              headers = vNode[property];
              break;
            }
            cells.push(cell);
          }
        }
        headers = (headers || []).concat(cells.filter(predicate));
        cells.forEach(function(tableCell) {
          var vNode = axe.utils.getNodeFromTree(tableCell);
          vNode[property] = headers;
        });
        return headers;
      }
      table.getHeaders = function(cell, tableGrid) {
        if (cell.getAttribute('headers')) {
          var headers = commons.dom.idrefs(cell, 'headers');
          if (headers.filter(function(header) {
            return header;
          }).length) {
            return headers;
          }
        }
        if (!tableGrid) {
          tableGrid = commons.table.toGrid(commons.dom.findUp(cell, 'table'));
        }
        var position = commons.table.getCellPosition(cell, tableGrid);
        var rowHeaders = traverseForHeaders('row', position, tableGrid);
        var colHeaders = traverseForHeaders('col', position, tableGrid);
        return [].concat(rowHeaders, colHeaders).reverse();
      };
      table.getScope = function(cell) {
        var scope = cell.getAttribute('scope');
        var role = cell.getAttribute('role');
        if (cell instanceof Element === false || [ 'TD', 'TH' ].indexOf(cell.nodeName.toUpperCase()) === -1) {
          throw new TypeError('Expected TD or TH element');
        }
        if (role === 'columnheader') {
          return 'col';
        } else if (role === 'rowheader') {
          return 'row';
        } else if (scope === 'col' || scope === 'row') {
          return scope;
        } else if (cell.nodeName.toUpperCase() !== 'TH') {
          return false;
        }
        var tableGrid = table.toGrid(dom.findUp(cell, 'table'));
        var pos = table.getCellPosition(cell, tableGrid);
        var headerRow = tableGrid[pos.y].reduce(function(headerRow, cell) {
          return headerRow && cell.nodeName.toUpperCase() === 'TH';
        }, true);
        if (headerRow) {
          return 'col';
        }
        var headerCol = tableGrid.map(function(col) {
          return col[pos.x];
        }).reduce(function(headerCol, cell) {
          return headerCol && cell && cell.nodeName.toUpperCase() === 'TH';
        }, true);
        if (headerCol) {
          return 'row';
        }
        return 'auto';
      };
      table.isColumnHeader = function(element) {
        return [ 'col', 'auto' ].indexOf(table.getScope(element)) !== -1;
      };
      table.isDataCell = function(cell) {
        if (!cell.children.length && !cell.textContent.trim()) {
          return false;
        }
        var role = cell.getAttribute('role');
        if (axe.commons.aria.isValidRole(role)) {
          return [ 'cell', 'gridcell' ].includes(role);
        } else {
          return cell.nodeName.toUpperCase() === 'TD';
        }
      };
      table.isDataTable = function(node) {
        var role = (node.getAttribute('role') || '').toLowerCase();
        if ((role === 'presentation' || role === 'none') && !dom.isFocusable(node)) {
          return false;
        }
        if (node.getAttribute('contenteditable') === 'true' || dom.findUp(node, '[contenteditable="true"]')) {
          return true;
        }
        if (role === 'grid' || role === 'treegrid' || role === 'table') {
          return true;
        }
        if (commons.aria.getRoleType(role) === 'landmark') {
          return true;
        }
        if (node.getAttribute('datatable') === '0') {
          return false;
        }
        if (node.getAttribute('summary')) {
          return true;
        }
        if (node.tHead || node.tFoot || node.caption) {
          return true;
        }
        for (var childIndex = 0, childLength = node.children.length; childIndex < childLength; childIndex++) {
          if (node.children[childIndex].nodeName.toUpperCase() === 'COLGROUP') {
            return true;
          }
        }
        var cells = 0;
        var rowLength = node.rows.length;
        var row, cell;
        var hasBorder = false;
        for (var rowIndex = 0; rowIndex < rowLength; rowIndex++) {
          row = node.rows[rowIndex];
          for (var cellIndex = 0, cellLength = row.cells.length; cellIndex < cellLength; cellIndex++) {
            cell = row.cells[cellIndex];
            if (cell.nodeName.toUpperCase() === 'TH') {
              return true;
            }
            if (!hasBorder && (cell.offsetWidth !== cell.clientWidth || cell.offsetHeight !== cell.clientHeight)) {
              hasBorder = true;
            }
            if (cell.getAttribute('scope') || cell.getAttribute('headers') || cell.getAttribute('abbr')) {
              return true;
            }
            if ([ 'columnheader', 'rowheader' ].includes((cell.getAttribute('role') || '').toLowerCase())) {
              return true;
            }
            if (cell.children.length === 1 && cell.children[0].nodeName.toUpperCase() === 'ABBR') {
              return true;
            }
            cells++;
          }
        }
        if (node.getElementsByTagName('table').length) {
          return false;
        }
        if (rowLength < 2) {
          return false;
        }
        var sampleRow = node.rows[Math.ceil(rowLength / 2)];
        if (sampleRow.cells.length === 1 && sampleRow.cells[0].colSpan === 1) {
          return false;
        }
        if (sampleRow.cells.length >= 5) {
          return true;
        }
        if (hasBorder) {
          return true;
        }
        var bgColor, bgImage;
        for (rowIndex = 0; rowIndex < rowLength; rowIndex++) {
          row = node.rows[rowIndex];
          if (bgColor && bgColor !== window.getComputedStyle(row).getPropertyValue('background-color')) {
            return true;
          } else {
            bgColor = window.getComputedStyle(row).getPropertyValue('background-color');
          }
          if (bgImage && bgImage !== window.getComputedStyle(row).getPropertyValue('background-image')) {
            return true;
          } else {
            bgImage = window.getComputedStyle(row).getPropertyValue('background-image');
          }
        }
        if (rowLength >= 20) {
          return true;
        }
        if (dom.getElementCoordinates(node).width > dom.getViewportSize(window).width * .95) {
          return false;
        }
        if (cells < 10) {
          return false;
        }
        if (node.querySelector('object, embed, iframe, applet')) {
          return false;
        }
        return true;
      };
      table.isHeader = function(cell) {
        if (table.isColumnHeader(cell) || table.isRowHeader(cell)) {
          return true;
        }
        if (cell.getAttribute('id')) {
          var id = axe.utils.escapeSelector(cell.getAttribute('id'));
          return !!document.querySelector('[headers~="'.concat(id, '"]'));
        }
        return false;
      };
      table.isRowHeader = function(cell) {
        return [ 'row', 'auto' ].includes(table.getScope(cell));
      };
      table.toGrid = axe.utils.memoize(function(node) {
        var table = [];
        var rows = node.rows;
        for (var i = 0, rowLength = rows.length; i < rowLength; i++) {
          var cells = rows[i].cells;
          table[i] = table[i] || [];
          var columnIndex = 0;
          for (var j = 0, cellLength = cells.length; j < cellLength; j++) {
            for (var colSpan = 0; colSpan < cells[j].colSpan; colSpan++) {
              for (var rowSpan = 0; rowSpan < cells[j].rowSpan; rowSpan++) {
                table[i + rowSpan] = table[i + rowSpan] || [];
                while (table[i + rowSpan][columnIndex]) {
                  columnIndex++;
                }
                table[i + rowSpan][columnIndex] = cells[j];
              }
              columnIndex++;
            }
          }
        }
        return table;
      });
      table.toArray = table.toGrid;
      (function(table) {
        var traverseTable = function traverseTable(dir, position, tableGrid, callback) {
          var result;
          var cell = tableGrid[position.y] ? tableGrid[position.y][position.x] : undefined;
          if (!cell) {
            return [];
          }
          if (typeof callback === 'function') {
            result = callback(cell, position, tableGrid);
            if (result === true) {
              return [ cell ];
            }
          }
          result = traverseTable(dir, {
            x: position.x + dir.x,
            y: position.y + dir.y
          }, tableGrid, callback);
          result.unshift(cell);
          return result;
        };
        table.traverse = function(dir, startPos, tableGrid, callback) {
          if (Array.isArray(startPos)) {
            callback = tableGrid;
            tableGrid = startPos;
            startPos = {
              x: 0,
              y: 0
            };
          }
          if (typeof dir === 'string') {
            switch (dir) {
             case 'left':
              dir = {
                x: -1,
                y: 0
              };
              break;

             case 'up':
              dir = {
                x: 0,
                y: -1
              };
              break;

             case 'right':
              dir = {
                x: 1,
                y: 0
              };
              break;

             case 'down':
              dir = {
                x: 0,
                y: 1
              };
              break;
            }
          }
          return traverseTable(dir, {
            x: startPos.x + dir.x,
            y: startPos.y + dir.y
          }, tableGrid, callback);
        };
      })(table);
      text.accessibleText = function accessibleText(element, context) {
        var virtualNode = axe.utils.getNodeFromTree(element);
        return text.accessibleTextVirtual(virtualNode, context);
      };
      text.accessibleTextVirtual = function accessibleTextVirtual(virtualNode) {
        var context = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
        var actualNode = virtualNode.actualNode;
        context = prepareContext(virtualNode, context);
        if (shouldIgnoreHidden(virtualNode, context)) {
          return '';
        }
        var computationSteps = [ aria.arialabelledbyText, aria.arialabelText, text.nativeTextAlternative, text.formControlValue, text.subtreeText, textNodeContent, text.titleText ];
        var accName = computationSteps.reduce(function(accName, step) {
          if (context.startNode === virtualNode) {
            accName = text.sanitize(accName);
          }
          if (accName !== '') {
            return accName;
          }
          return step(virtualNode, context);
        }, '');
        if (context.debug) {
          axe.log(accName || '{empty-value}', actualNode, context);
        }
        return accName;
      };
      function textNodeContent(_ref42) {
        var actualNode = _ref42.actualNode;
        if (actualNode.nodeType !== 3) {
          return '';
        }
        return actualNode.textContent;
      }
      function shouldIgnoreHidden(_ref43, context) {
        var actualNode = _ref43.actualNode;
        if (actualNode.nodeType !== 1 || context.includeHidden) {
          return false;
        }
        return !dom.isVisible(actualNode, true);
      }
      function prepareContext(virtualNode, context) {
        var actualNode = virtualNode.actualNode;
        if (!context.startNode) {
          context = _extends({
            startNode: virtualNode
          }, context);
        }
        if (actualNode.nodeType === 1 && context.inLabelledByContext && context.includeHidden === undefined) {
          context = _extends({
            includeHidden: !dom.isVisible(actualNode, true)
          }, context);
        }
        return context;
      }
      text.accessibleTextVirtual.alreadyProcessed = function alreadyProcessed(virtualnode, context) {
        context.processed = context.processed || [];
        if (context.processed.includes(virtualnode)) {
          return true;
        }
        context.processed.push(virtualnode);
        return false;
      };
      var controlValueRoles = [ 'textbox', 'progressbar', 'scrollbar', 'slider', 'spinbutton', 'combobox', 'listbox' ];
      text.formControlValueMethods = {
        nativeTextboxValue: nativeTextboxValue,
        nativeSelectValue: nativeSelectValue,
        ariaTextboxValue: ariaTextboxValue,
        ariaListboxValue: ariaListboxValue,
        ariaComboboxValue: ariaComboboxValue,
        ariaRangeValue: ariaRangeValue
      };
      text.formControlValue = function formControlValue(virtualNode) {
        var context = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
        var actualNode = virtualNode.actualNode;
        var unsupported = text.unsupported.accessibleNameFromFieldValue || [];
        var role = aria.getRole(actualNode);
        if (context.startNode === virtualNode || !controlValueRoles.includes(role) || unsupported.includes(role)) {
          return '';
        }
        var valueMethods = Object.keys(text.formControlValueMethods).map(function(name) {
          return text.formControlValueMethods[name];
        });
        var valueString = valueMethods.reduce(function(accName, step) {
          return accName || step(virtualNode, context);
        }, '');
        if (context.debug) {
          axe.log(valueString || '{empty-value}', actualNode, context);
        }
        return valueString;
      };
      function nativeTextboxValue(node) {
        node = node.actualNode || node;
        if (axe.commons.forms.isNativeTextbox(node)) {
          return node.value || '';
        }
        return '';
      }
      function nativeSelectValue(node) {
        node = node.actualNode || node;
        if (!axe.commons.forms.isNativeSelect(node)) {
          return '';
        }
        return Array.from(node.options).filter(function(option) {
          return option.selected;
        }).map(function(option) {
          return option.text;
        }).join(' ') || '';
      }
      function ariaTextboxValue(virtualNode) {
        var actualNode = virtualNode.actualNode;
        if (!axe.commons.forms.isAriaTextbox(actualNode)) {
          return '';
        }
        if (!dom.isHiddenWithCSS(actualNode)) {
          return text.visibleVirtual(virtualNode, true);
        } else {
          return actualNode.textContent;
        }
      }
      function ariaListboxValue(virtualNode, context) {
        var actualNode = virtualNode.actualNode;
        if (!axe.commons.forms.isAriaListbox(actualNode)) {
          return '';
        }
        var selected = aria.getOwnedVirtual(virtualNode).filter(function(owned) {
          return aria.getRole(owned) === 'option' && owned.actualNode.getAttribute('aria-selected') === 'true';
        });
        if (selected.length === 0) {
          return '';
        }
        return axe.commons.text.accessibleTextVirtual(selected[0], context);
      }
      function ariaComboboxValue(virtualNode, context) {
        var actualNode = virtualNode.actualNode;
        var listbox;
        if (!axe.commons.forms.isAriaCombobox(actualNode)) {
          return '';
        }
        listbox = aria.getOwnedVirtual(virtualNode).filter(function(elm) {
          return aria.getRole(elm) === 'listbox';
        })[0];
        return listbox ? text.formControlValueMethods.ariaListboxValue(listbox, context) : '';
      }
      function ariaRangeValue(node) {
        node = node.actualNode || node;
        if (!axe.commons.forms.isAriaRange(node) || !node.hasAttribute('aria-valuenow')) {
          return '';
        }
        var valueNow = +node.getAttribute('aria-valuenow');
        return !isNaN(valueNow) ? String(valueNow) : '0';
      }
      text.isHumanInterpretable = function(str) {
        if (!str.length) {
          return 0;
        }
        var alphaNumericIconMap = [ 'x', 'i' ];
        if (alphaNumericIconMap.includes(str)) {
          return 0;
        }
        var noUnicodeStr = text.removeUnicode(str, {
          emoji: true,
          nonBmp: true,
          punctuations: true
        });
        if (!text.sanitize(noUnicodeStr)) {
          return 0;
        }
        return 1;
      };
      text.isIconLigature = function(textVNode) {
        var differenceThreshold = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : .15;
        var occuranceThreshold = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : 3;
        var nodeValue = textVNode.actualNode.nodeValue.trim();
        if (!text.sanitize(nodeValue) || text.hasUnicode(nodeValue, {
          emoji: true,
          nonBmp: true
        })) {
          return false;
        }
        if (!axe._cache.get('canvasContext')) {
          axe._cache.set('canvasContext', document.createElement('canvas').getContext('2d'));
        }
        var canvasContext = axe._cache.get('canvasContext');
        var canvas = canvasContext.canvas;
        if (!axe._cache.get('fonts')) {
          axe._cache.set('fonts', {});
        }
        var fonts = axe._cache.get('fonts');
        var style = window.getComputedStyle(textVNode.parent.actualNode);
        var fontFamily = style.getPropertyValue('font-family');
        if (!fonts[fontFamily]) {
          fonts[fontFamily] = {
            occurances: 0,
            numLigatures: 0
          };
        }
        var font = fonts[fontFamily];
        if (font.occurances >= occuranceThreshold) {
          if (font.numLigatures / font.occurances === 1) {
            return true;
          } else if (font.numLigatures === 0) {
            return false;
          }
        }
        font.occurances++;
        var fontSize = 30;
        var fontStyle = ''.concat(fontSize, 'px ').concat(fontFamily);
        canvasContext.font = fontStyle;
        var firstChar = nodeValue.charAt(0);
        var width = canvasContext.measureText(firstChar).width;
        if (width < 30) {
          var diff = 30 / width;
          width *= diff;
          fontSize *= diff;
          fontStyle = ''.concat(fontSize, 'px ').concat(fontFamily);
        }
        canvas.width = width;
        canvas.height = fontSize;
        canvasContext.font = fontStyle;
        canvasContext.textAlign = 'left';
        canvasContext.textBaseline = 'top';
        canvasContext.fillText(firstChar, 0, 0);
        var compareData = new Uint32Array(canvasContext.getImageData(0, 0, width, fontSize).data.buffer);
        if (!compareData.some(function(pixel) {
          return pixel;
        })) {
          font.numLigatures++;
          return true;
        }
        canvasContext.clearRect(0, 0, width, fontSize);
        canvasContext.fillText(nodeValue, 0, 0);
        var compareWith = new Uint32Array(canvasContext.getImageData(0, 0, width, fontSize).data.buffer);
        var differences = compareData.reduce(function(diff, pixel, i) {
          if (pixel === 0 && compareWith[i] === 0) {
            return diff;
          }
          if (pixel !== 0 && compareWith[i] !== 0) {
            return diff;
          }
          return ++diff;
        }, 0);
        var expectedWidth = nodeValue.split('').reduce(function(width, _char) {
          return width + canvasContext.measureText(_char).width;
        }, 0);
        var actualWidth = canvasContext.measureText(nodeValue).width;
        var pixelDifference = differences / compareData.length;
        var sizeDifference = 1 - actualWidth / expectedWidth;
        if (pixelDifference >= differenceThreshold && sizeDifference >= differenceThreshold) {
          font.numLigatures++;
          return true;
        }
        return false;
      };
      var autocomplete = {
        stateTerms: [ 'on', 'off' ],
        standaloneTerms: [ 'name', 'honorific-prefix', 'given-name', 'additional-name', 'family-name', 'honorific-suffix', 'nickname', 'username', 'new-password', 'current-password', 'organization-title', 'organization', 'street-address', 'address-line1', 'address-line2', 'address-line3', 'address-level4', 'address-level3', 'address-level2', 'address-level1', 'country', 'country-name', 'postal-code', 'cc-name', 'cc-given-name', 'cc-additional-name', 'cc-family-name', 'cc-number', 'cc-exp', 'cc-exp-month', 'cc-exp-year', 'cc-csc', 'cc-type', 'transaction-currency', 'transaction-amount', 'language', 'bday', 'bday-day', 'bday-month', 'bday-year', 'sex', 'url', 'photo' ],
        qualifiers: [ 'home', 'work', 'mobile', 'fax', 'pager' ],
        qualifiedTerms: [ 'tel', 'tel-country-code', 'tel-national', 'tel-area-code', 'tel-local', 'tel-local-prefix', 'tel-local-suffix', 'tel-extension', 'email', 'impp' ],
        locations: [ 'billing', 'shipping' ]
      };
      text.autocomplete = autocomplete;
      text.isValidAutocomplete = function isValidAutocomplete(autocomplete) {
        var _ref44 = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {}, _ref44$looseTyped = _ref44.looseTyped, looseTyped = _ref44$looseTyped === void 0 ? false : _ref44$looseTyped, _ref44$stateTerms = _ref44.stateTerms, stateTerms = _ref44$stateTerms === void 0 ? [] : _ref44$stateTerms, _ref44$locations = _ref44.locations, locations = _ref44$locations === void 0 ? [] : _ref44$locations, _ref44$qualifiers = _ref44.qualifiers, qualifiers = _ref44$qualifiers === void 0 ? [] : _ref44$qualifiers, _ref44$standaloneTerm = _ref44.standaloneTerms, standaloneTerms = _ref44$standaloneTerm === void 0 ? [] : _ref44$standaloneTerm, _ref44$qualifiedTerms = _ref44.qualifiedTerms, qualifiedTerms = _ref44$qualifiedTerms === void 0 ? [] : _ref44$qualifiedTerms;
        autocomplete = autocomplete.toLowerCase().trim();
        stateTerms = stateTerms.concat(text.autocomplete.stateTerms);
        if (stateTerms.includes(autocomplete) || autocomplete === '') {
          return true;
        }
        qualifiers = qualifiers.concat(text.autocomplete.qualifiers);
        locations = locations.concat(text.autocomplete.locations);
        standaloneTerms = standaloneTerms.concat(text.autocomplete.standaloneTerms);
        qualifiedTerms = qualifiedTerms.concat(text.autocomplete.qualifiedTerms);
        var autocompleteTerms = autocomplete.split(/\s+/g);
        if (!looseTyped) {
          if (autocompleteTerms[0].length > 8 && autocompleteTerms[0].substr(0, 8) === 'section-') {
            autocompleteTerms.shift();
          }
          if (locations.includes(autocompleteTerms[0])) {
            autocompleteTerms.shift();
          }
          if (qualifiers.includes(autocompleteTerms[0])) {
            autocompleteTerms.shift();
            standaloneTerms = [];
          }
          if (autocompleteTerms.length !== 1) {
            return false;
          }
        }
        var purposeTerm = autocompleteTerms[autocompleteTerms.length - 1];
        return standaloneTerms.includes(purposeTerm) || qualifiedTerms.includes(purposeTerm);
      };
      text.labelText = function labelText(virtualNode) {
        var context = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
        var alreadyProcessed = text.accessibleTextVirtual.alreadyProcessed;
        if (context.inControlContext || context.inLabelledByContext || alreadyProcessed(virtualNode, context)) {
          return '';
        }
        if (!context.startNode) {
          context.startNode = virtualNode;
        }
        var labelContext = _extends({
          inControlContext: true
        }, context);
        var explicitLabels = getExplicitLabels(virtualNode);
        var implicitLabel = dom.findUpVirtual(virtualNode, 'label');
        var labels;
        if (implicitLabel) {
          labels = [].concat(_toConsumableArray(explicitLabels), [ implicitLabel ]);
          labels.sort(axe.utils.nodeSorter);
        } else {
          labels = explicitLabels;
        }
        return labels.map(function(label) {
          return text.accessibleText(label, labelContext);
        }).filter(function(text) {
          return text !== '';
        }).join(' ');
      };
      function getExplicitLabels(_ref45) {
        var actualNode = _ref45.actualNode;
        if (!actualNode.id) {
          return [];
        }
        return dom.findElmsInContext({
          elm: 'label',
          attr: 'for',
          value: actualNode.id,
          context: actualNode
        });
      }
      text.labelVirtual = function(node) {
        var ref, candidate, doc;
        candidate = aria.labelVirtual(node);
        if (candidate) {
          return candidate;
        }
        if (node.actualNode.id) {
          var id = axe.utils.escapeSelector(node.actualNode.getAttribute('id'));
          doc = axe.commons.dom.getRootNode(node.actualNode);
          ref = doc.querySelector('label[for="' + id + '"]');
          candidate = ref && text.visible(ref, true);
          if (candidate) {
            return candidate;
          }
        }
        ref = dom.findUpVirtual(node, 'label');
        candidate = ref && text.visible(ref, true);
        if (candidate) {
          return candidate;
        }
        return null;
      };
      text.label = function(node) {
        node = axe.utils.getNodeFromTree(node);
        return text.labelVirtual(node);
      };
      text.nativeElementType = [ {
        matches: [ {
          nodeName: 'textarea'
        }, {
          nodeName: 'input',
          properties: {
            type: [ 'text', 'password', 'search', 'tel', 'email', 'url' ]
          }
        } ],
        namingMethods: 'labelText'
      }, {
        matches: {
          nodeName: 'input',
          properties: {
            type: [ 'button', 'submit', 'reset' ]
          }
        },
        namingMethods: [ 'valueText', 'titleText', 'buttonDefaultText' ]
      }, {
        matches: {
          nodeName: 'input',
          properties: {
            type: 'image'
          }
        },
        namingMethods: [ 'altText', 'valueText', 'labelText', 'titleText', 'buttonDefaultText' ]
      }, {
        matches: 'button',
        namingMethods: 'subtreeText'
      }, {
        matches: 'fieldset',
        namingMethods: 'fieldsetLegendText'
      }, {
        matches: 'OUTPUT',
        namingMethods: 'subtreeText'
      }, {
        matches: [ {
          nodeName: 'select'
        }, {
          nodeName: 'input',
          properties: {
            type: /^(?!text|password|search|tel|email|url|button|submit|reset)/
          }
        } ],
        namingMethods: 'labelText'
      }, {
        matches: 'summary',
        namingMethods: 'subtreeText'
      }, {
        matches: 'figure',
        namingMethods: [ 'figureText', 'titleText' ]
      }, {
        matches: 'img',
        namingMethods: 'altText'
      }, {
        matches: 'table',
        namingMethods: [ 'tableCaptionText', 'tableSummaryText' ]
      }, {
        matches: [ 'hr', 'br' ],
        namingMethods: [ 'titleText', 'singleSpace' ]
      } ];
      text.nativeTextAlternative = function nativeTextAlternative(virtualNode) {
        var context = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
        var actualNode = virtualNode.actualNode;
        if (actualNode.nodeType !== 1 || [ 'presentation', 'none' ].includes(aria.getRole(actualNode))) {
          return '';
        }
        var textMethods = findTextMethods(virtualNode);
        var accName = textMethods.reduce(function(accName, step) {
          return accName || step(virtualNode, context);
        }, '');
        if (context.debug) {
          axe.log(accName || '{empty-value}', actualNode, context);
        }
        return accName;
      };
      function findTextMethods(virtualNode) {
        var nativeElementType = text.nativeElementType, nativeTextMethods = text.nativeTextMethods;
        var nativeType = nativeElementType.find(function(_ref46) {
          var matches = _ref46.matches;
          return axe.commons.matches(virtualNode, matches);
        });
        var methods = nativeType ? [].concat(nativeType.namingMethods) : [];
        return methods.map(function(methodName) {
          return nativeTextMethods[methodName];
        });
      }
      var defaultButtonValues = {
        submit: 'Submit',
        image: 'Submit',
        reset: 'Reset',
        button: ''
      };
      text.nativeTextMethods = {
        valueText: function valueText(_ref47) {
          var actualNode = _ref47.actualNode;
          return actualNode.value || '';
        },
        buttonDefaultText: function buttonDefaultText(_ref48) {
          var actualNode = _ref48.actualNode;
          return defaultButtonValues[actualNode.type] || '';
        },
        tableCaptionText: descendantText.bind(null, 'caption'),
        figureText: descendantText.bind(null, 'figcaption'),
        fieldsetLegendText: descendantText.bind(null, 'legend'),
        altText: attrText.bind(null, 'alt'),
        tableSummaryText: attrText.bind(null, 'summary'),
        titleText: function titleText(virtualNode, context) {
          return text.titleText(virtualNode, context);
        },
        subtreeText: function subtreeText(virtualNode, context) {
          return text.subtreeText(virtualNode, context);
        },
        labelText: function labelText(virtualNode, context) {
          return text.labelText(virtualNode, context);
        },
        singleSpace: function singleSpace() {
          return ' ';
        }
      };
      function attrText(attr, _ref49) {
        var actualNode = _ref49.actualNode;
        return actualNode.getAttribute(attr) || '';
      }
      function descendantText(nodeName, _ref50, context) {
        var actualNode = _ref50.actualNode;
        nodeName = nodeName.toLowerCase();
        var nodeNames = [ nodeName, actualNode.nodeName.toLowerCase() ].join(',');
        var candidate = actualNode.querySelector(nodeNames);
        if (!candidate || candidate.nodeName.toLowerCase() !== nodeName) {
          return '';
        }
        return text.accessibleText(candidate, context);
      }
      text.sanitize = function(str) {
        'use strict';
        return str.replace(/\r\n/g, '\n').replace(/\u00A0/g, ' ').replace(/[\s]{2,}/g, ' ').trim();
      };
      text.subtreeText = function subtreeText(virtualNode) {
        var context = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
        var alreadyProcessed = text.accessibleTextVirtual.alreadyProcessed;
        context.startNode = context.startNode || virtualNode;
        var strict = context.strict;
        if (alreadyProcessed(virtualNode, context) || !aria.namedFromContents(virtualNode, {
          strict: strict
        })) {
          return '';
        }
        return aria.getOwnedVirtual(virtualNode).reduce(function(contentText, child) {
          return appendAccessibleText(contentText, child, context);
        }, '');
      };
      var phrasingElements = [ 'A', 'EM', 'STRONG', 'SMALL', 'MARK', 'ABBR', 'DFN', 'I', 'B', 'S', 'U', 'CODE', 'VAR', 'SAMP', 'KBD', 'SUP', 'SUB', 'Q', 'CITE', 'SPAN', 'BDO', 'BDI', 'WBR', 'INS', 'DEL', 'MAP', 'AREA', 'NOSCRIPT', 'RUBY', 'BUTTON', 'LABEL', 'OUTPUT', 'DATALIST', 'KEYGEN', 'PROGRESS', 'COMMAND', 'CANVAS', 'TIME', 'METER', '#TEXT' ];
      function appendAccessibleText(contentText, virtualNode, context) {
        var nodeName = virtualNode.actualNode.nodeName.toUpperCase();
        var contentTextAdd = text.accessibleTextVirtual(virtualNode, context);
        if (!contentTextAdd) {
          return contentText;
        }
        if (!phrasingElements.includes(nodeName)) {
          if (contentTextAdd[0] !== ' ') {
            contentTextAdd += ' ';
          }
          if (contentText && contentText[contentText.length - 1] !== ' ') {
            contentTextAdd = ' ' + contentTextAdd;
          }
        }
        return contentText + contentTextAdd;
      }
      var alwaysTitleElements = [ 'button', 'iframe', 'a[href]', {
        nodeName: 'input',
        properties: {
          type: 'button'
        }
      } ];
      text.titleText = function titleText(node) {
        node = node.actualNode || node;
        if (node.nodeType !== 1 || !node.hasAttribute('title')) {
          return '';
        }
        if (!axe.commons.matches(node, alwaysTitleElements) && [ 'none', 'presentation' ].includes(aria.getRole(node))) {
          return '';
        }
        return node.getAttribute('title');
      };
      text.hasUnicode = function hasUnicode(str, options) {
        var emoji = options.emoji, nonBmp = options.nonBmp, punctuations = options.punctuations;
        if (emoji) {
          return axe.imports.emojiRegexText().test(str);
        }
        if (nonBmp) {
          return getUnicodeNonBmpRegExp().test(str) || getSupplementaryPrivateUseRegExp().test(str);
        }
        if (punctuations) {
          return getPunctuationRegExp().test(str);
        }
        return false;
      };
      text.removeUnicode = function removeUnicode(str, options) {
        var emoji = options.emoji, nonBmp = options.nonBmp, punctuations = options.punctuations;
        if (emoji) {
          str = str.replace(axe.imports.emojiRegexText(), '');
        }
        if (nonBmp) {
          str = str.replace(getUnicodeNonBmpRegExp(), '');
          str = str.replace(getSupplementaryPrivateUseRegExp(), '');
        }
        if (punctuations) {
          str = str.replace(getPunctuationRegExp(), '');
        }
        return str;
      };
      function getUnicodeNonBmpRegExp() {
        return /[\u1D00-\u1D7F\u1D80-\u1DBF\u1DC0-\u1DFF\u20A0-\u20CF\u20D0-\u20FF\u2100-\u214F\u2150-\u218F\u2190-\u21FF\u2200-\u22FF\u2300-\u23FF\u2400-\u243F\u2440-\u245F\u2460-\u24FF\u2500-\u257F\u2580-\u259F\u25A0-\u25FF\u2600-\u26FF\u2700-\u27BF\uE000-\uF8FF]/g;
      }
      function getPunctuationRegExp() {
        return /[\u2000-\u206F\u2E00-\u2E7F\\'!"#$%&\xa3\xa2\xa5\xa7\u20ac()*+,\-.\/:;<=>?@\[\]^_`{|}~\xb1]/g;
      }
      function getSupplementaryPrivateUseRegExp() {
        return /[\uDB80-\uDBBF][\uDC00-\uDFFF]/g;
      }
      text.unsupported = {
        accessibleNameFromFieldValue: [ 'combobox', 'listbox', 'progressbar' ]
      };
      text.visibleTextNodes = function(vNode) {
        var parentVisible = axe.commons.dom.isVisible(vNode.actualNode);
        var nodes = [];
        vNode.children.forEach(function(child) {
          if (child.actualNode.nodeType === 3) {
            if (parentVisible) {
              nodes.push(child);
            }
          } else {
            nodes = nodes.concat(text.visibleTextNodes(child));
          }
        });
        return nodes;
      };
      text.visibleVirtual = function(element, screenReader, noRecursing) {
        var result = element.children.map(function(child) {
          if (child.actualNode.nodeType === 3) {
            var nodeValue = child.actualNode.nodeValue;
            if (nodeValue && dom.isVisible(element.actualNode, screenReader)) {
              return nodeValue;
            }
          } else if (!noRecursing) {
            return text.visibleVirtual(child, screenReader);
          }
        }).join('');
        return text.sanitize(result);
      };
      text.visible = function(element, screenReader, noRecursing) {
        element = axe.utils.getNodeFromTree(element);
        return text.visibleVirtual(element, screenReader, noRecursing);
      };
      return commons;
    }()
  });
})(typeof window === 'object' ? window : this);