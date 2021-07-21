"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SubscriptionServer = void 0;
var WebSocket = require("ws");
var message_types_1 = require("./message-types");
var protocol_1 = require("./protocol");
var is_object_1 = require("./utils/is-object");
var graphql_1 = require("graphql");
var empty_iterable_1 = require("./utils/empty-iterable");
var iterall_1 = require("iterall");
var is_subscriptions_1 = require("./utils/is-subscriptions");
var parse_legacy_protocol_1 = require("./legacy/parse-legacy-protocol");
var isWebSocketServer = function (socket) { return socket.on; };
var SubscriptionServer = (function () {
    function SubscriptionServer(options, socketOptionsOrServer) {
        var _this = this;
        var onOperation = options.onOperation, onOperationComplete = options.onOperationComplete, onConnect = options.onConnect, onDisconnect = options.onDisconnect, keepAlive = options.keepAlive;
        this.specifiedRules = options.validationRules || graphql_1.specifiedRules;
        this.loadExecutor(options);
        this.onOperation = onOperation;
        this.onOperationComplete = onOperationComplete;
        this.onConnect = onConnect;
        this.onDisconnect = onDisconnect;
        this.keepAlive = keepAlive;
        if (isWebSocketServer(socketOptionsOrServer)) {
            this.wsServer = socketOptionsOrServer;
        }
        else {
            this.wsServer = new WebSocket.Server(socketOptionsOrServer || {});
        }
        var connectionHandler = (function (socket, request) {
            socket.upgradeReq = request;
            if (socket.protocol === undefined ||
                (socket.protocol.indexOf(protocol_1.GRAPHQL_WS) === -1 && socket.protocol.indexOf(protocol_1.GRAPHQL_SUBSCRIPTIONS) === -1)) {
                socket.close(1002);
                return;
            }
            var connectionContext = Object.create(null);
            connectionContext.initPromise = Promise.resolve(true);
            connectionContext.isLegacy = false;
            connectionContext.socket = socket;
            connectionContext.request = request;
            connectionContext.operations = {};
            var connectionClosedHandler = function (error) {
                if (error) {
                    _this.sendError(connectionContext, '', { message: error.message ? error.message : error }, message_types_1.default.GQL_CONNECTION_ERROR);
                    setTimeout(function () {
                        connectionContext.socket.close(1011);
                    }, 10);
                }
                _this.onClose(connectionContext);
                if (_this.onDisconnect) {
                    _this.onDisconnect(socket, connectionContext);
                }
            };
            socket.on('error', connectionClosedHandler);
            socket.on('close', connectionClosedHandler);
            socket.on('message', _this.onMessage(connectionContext));
        });
        this.wsServer.on('connection', connectionHandler);
        this.closeHandler = function () {
            _this.wsServer.removeListener('connection', connectionHandler);
            _this.wsServer.close();
        };
    }
    SubscriptionServer.create = function (options, socketOptionsOrServer) {
        return new SubscriptionServer(options, socketOptionsOrServer);
    };
    Object.defineProperty(SubscriptionServer.prototype, "server", {
        get: function () {
            return this.wsServer;
        },
        enumerable: false,
        configurable: true
    });
    SubscriptionServer.prototype.close = function () {
        this.closeHandler();
    };
    SubscriptionServer.prototype.loadExecutor = function (options) {
        var execute = options.execute, subscribe = options.subscribe, schema = options.schema, rootValue = options.rootValue;
        if (!execute) {
            throw new Error('Must provide `execute` for websocket server constructor.');
        }
        this.schema = schema;
        this.rootValue = rootValue;
        this.execute = execute;
        this.subscribe = subscribe;
    };
    SubscriptionServer.prototype.unsubscribe = function (connectionContext, opId) {
        if (connectionContext.operations && connectionContext.operations[opId]) {
            if (connectionContext.operations[opId].return) {
                connectionContext.operations[opId].return();
            }
            delete connectionContext.operations[opId];
            if (this.onOperationComplete) {
                this.onOperationComplete(connectionContext.socket, opId);
            }
        }
    };
    SubscriptionServer.prototype.onClose = function (connectionContext) {
        var _this = this;
        Object.keys(connectionContext.operations).forEach(function (opId) {
            _this.unsubscribe(connectionContext, opId);
        });
    };
    SubscriptionServer.prototype.onMessage = function (connectionContext) {
        var _this = this;
        return function (message) {
            var parsedMessage;
            try {
                parsedMessage = parse_legacy_protocol_1.parseLegacyProtocolMessage(connectionContext, JSON.parse(message));
            }
            catch (e) {
                _this.sendError(connectionContext, null, { message: e.message }, message_types_1.default.GQL_CONNECTION_ERROR);
                return;
            }
            var opId = parsedMessage.id;
            switch (parsedMessage.type) {
                case message_types_1.default.GQL_CONNECTION_INIT:
                    if (_this.onConnect) {
                        connectionContext.initPromise = new Promise(function (resolve, reject) {
                            try {
                                resolve(_this.onConnect(parsedMessage.payload, connectionContext.socket, connectionContext));
                            }
                            catch (e) {
                                reject(e);
                            }
                        });
                    }
                    connectionContext.initPromise.then(function (result) {
                        if (result === false) {
                            throw new Error('Prohibited connection!');
                        }
                        _this.sendMessage(connectionContext, undefined, message_types_1.default.GQL_CONNECTION_ACK, undefined);
                        if (_this.keepAlive) {
                            _this.sendKeepAlive(connectionContext);
                            var keepAliveTimer_1 = setInterval(function () {
                                if (connectionContext.socket.readyState === WebSocket.OPEN) {
                                    _this.sendKeepAlive(connectionContext);
                                }
                                else {
                                    clearInterval(keepAliveTimer_1);
                                }
                            }, _this.keepAlive);
                        }
                    }).catch(function (error) {
                        _this.sendError(connectionContext, opId, { message: error.message }, message_types_1.default.GQL_CONNECTION_ERROR);
                        setTimeout(function () {
                            connectionContext.socket.close(1011);
                        }, 10);
                    });
                    break;
                case message_types_1.default.GQL_CONNECTION_TERMINATE:
                    connectionContext.socket.close();
                    break;
                case message_types_1.default.GQL_START:
                    connectionContext.initPromise.then(function (initResult) {
                        if (connectionContext.operations && connectionContext.operations[opId]) {
                            _this.unsubscribe(connectionContext, opId);
                        }
                        var baseParams = {
                            query: parsedMessage.payload.query,
                            variables: parsedMessage.payload.variables,
                            operationName: parsedMessage.payload.operationName,
                            context: is_object_1.default(initResult) ? Object.assign(Object.create(Object.getPrototypeOf(initResult)), initResult) : {},
                            formatResponse: undefined,
                            formatError: undefined,
                            callback: undefined,
                            schema: _this.schema,
                        };
                        var promisedParams = Promise.resolve(baseParams);
                        connectionContext.operations[opId] = empty_iterable_1.createEmptyIterable();
                        if (_this.onOperation) {
                            var messageForCallback = parsedMessage;
                            promisedParams = Promise.resolve(_this.onOperation(messageForCallback, baseParams, connectionContext.socket));
                        }
                        return promisedParams.then(function (params) {
                            if (typeof params !== 'object') {
                                var error = "Invalid params returned from onOperation! return values must be an object!";
                                _this.sendError(connectionContext, opId, { message: error });
                                throw new Error(error);
                            }
                            if (!params.schema) {
                                var error = 'Missing schema information. The GraphQL schema should be provided either statically in' +
                                    ' the `SubscriptionServer` constructor or as a property on the object returned from onOperation!';
                                _this.sendError(connectionContext, opId, { message: error });
                                throw new Error(error);
                            }
                            var document = typeof baseParams.query !== 'string' ? baseParams.query : graphql_1.parse(baseParams.query);
                            var executionPromise;
                            var validationErrors = graphql_1.validate(params.schema, document, _this.specifiedRules);
                            if (validationErrors.length > 0) {
                                executionPromise = Promise.resolve({ errors: validationErrors });
                            }
                            else {
                                var executor = _this.execute;
                                if (_this.subscribe && is_subscriptions_1.isASubscriptionOperation(document, params.operationName)) {
                                    executor = _this.subscribe;
                                }
                                executionPromise = Promise.resolve(executor(params.schema, document, _this.rootValue, params.context, params.variables, params.operationName));
                            }
                            return executionPromise.then(function (executionResult) { return ({
                                executionIterable: iterall_1.isAsyncIterable(executionResult) ?
                                    executionResult : iterall_1.createAsyncIterator([executionResult]),
                                params: params,
                            }); });
                        }).then(function (_a) {
                            var executionIterable = _a.executionIterable, params = _a.params;
                            iterall_1.forAwaitEach(executionIterable, function (value) {
                                var result = value;
                                if (params.formatResponse) {
                                    try {
                                        result = params.formatResponse(value, params);
                                    }
                                    catch (err) {
                                        console.error('Error in formatResponse function:', err);
                                    }
                                }
                                _this.sendMessage(connectionContext, opId, message_types_1.default.GQL_DATA, result);
                            })
                                .then(function () {
                                _this.sendMessage(connectionContext, opId, message_types_1.default.GQL_COMPLETE, null);
                            })
                                .catch(function (e) {
                                var error = e;
                                if (params.formatError) {
                                    try {
                                        error = params.formatError(e, params);
                                    }
                                    catch (err) {
                                        console.error('Error in formatError function: ', err);
                                    }
                                }
                                if (Object.keys(error).length === 0) {
                                    error = { name: error.name, message: error.message };
                                }
                                _this.sendError(connectionContext, opId, error);
                            });
                            return executionIterable;
                        }).then(function (subscription) {
                            connectionContext.operations[opId] = subscription;
                        }).then(function () {
                            _this.sendMessage(connectionContext, opId, message_types_1.default.SUBSCRIPTION_SUCCESS, undefined);
                        }).catch(function (e) {
                            if (e.errors) {
                                _this.sendMessage(connectionContext, opId, message_types_1.default.GQL_DATA, { errors: e.errors });
                            }
                            else {
                                _this.sendError(connectionContext, opId, { message: e.message });
                            }
                            _this.unsubscribe(connectionContext, opId);
                            return;
                        });
                    }).catch(function (error) {
                        _this.sendError(connectionContext, opId, { message: error.message });
                        _this.unsubscribe(connectionContext, opId);
                    });
                    break;
                case message_types_1.default.GQL_STOP:
                    _this.unsubscribe(connectionContext, opId);
                    break;
                default:
                    _this.sendError(connectionContext, opId, { message: 'Invalid message type!' });
            }
        };
    };
    SubscriptionServer.prototype.sendKeepAlive = function (connectionContext) {
        if (connectionContext.isLegacy) {
            this.sendMessage(connectionContext, undefined, message_types_1.default.KEEP_ALIVE, undefined);
        }
        else {
            this.sendMessage(connectionContext, undefined, message_types_1.default.GQL_CONNECTION_KEEP_ALIVE, undefined);
        }
    };
    SubscriptionServer.prototype.sendMessage = function (connectionContext, opId, type, payload) {
        var parsedMessage = parse_legacy_protocol_1.parseLegacyProtocolMessage(connectionContext, {
            type: type,
            id: opId,
            payload: payload,
        });
        if (parsedMessage && connectionContext.socket.readyState === WebSocket.OPEN) {
            connectionContext.socket.send(JSON.stringify(parsedMessage));
        }
    };
    SubscriptionServer.prototype.sendError = function (connectionContext, opId, errorPayload, overrideDefaultErrorType) {
        var sanitizedOverrideDefaultErrorType = overrideDefaultErrorType || message_types_1.default.GQL_ERROR;
        if ([
            message_types_1.default.GQL_CONNECTION_ERROR,
            message_types_1.default.GQL_ERROR,
        ].indexOf(sanitizedOverrideDefaultErrorType) === -1) {
            throw new Error('overrideDefaultErrorType should be one of the allowed error messages' +
                ' GQL_CONNECTION_ERROR or GQL_ERROR');
        }
        this.sendMessage(connectionContext, opId, sanitizedOverrideDefaultErrorType, errorPayload);
    };
    return SubscriptionServer;
}());
exports.SubscriptionServer = SubscriptionServer;
//# sourceMappingURL=server.js.map