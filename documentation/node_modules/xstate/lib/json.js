"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.jsonify = exports.parse = exports.stringify = exports.machineToJSON = exports.stringifyFunction = void 0;
var utils_1 = require("./utils");
// tslint:disable-next-line:ban-types
function stringifyFunction(fn) {
    return {
        $function: fn.toString()
    };
}
exports.stringifyFunction = stringifyFunction;
function getStateNodeId(stateNode) {
    return "#" + stateNode.id;
}
// derive config from machine
function machineToJSON(stateNode) {
    var config = {
        type: stateNode.type,
        initial: stateNode.initial === undefined ? undefined : String(stateNode.initial),
        id: stateNode.id,
        key: stateNode.key,
        entry: stateNode.onEntry,
        exit: stateNode.onExit,
        on: utils_1.mapValues(stateNode.on, function (transition) {
            return transition.map(function (t) {
                return {
                    target: t.target ? t.target.map(getStateNodeId) : [],
                    source: getStateNodeId(t.source),
                    actions: t.actions,
                    cond: t.cond,
                    eventType: t.eventType
                };
            });
        }),
        invoke: stateNode.invoke,
        states: {}
    };
    Object.values(stateNode.states).forEach(function (sn) {
        config.states[sn.key] = machineToJSON(sn);
    });
    return config;
}
exports.machineToJSON = machineToJSON;
function stringify(machine) {
    return JSON.stringify(machineToJSON(machine), function (_, value) {
        if (utils_1.isFunction(value)) {
            return { $function: value.toString() };
        }
        return value;
    });
}
exports.stringify = stringify;
function parse(machineString) {
    var config = JSON.parse(machineString, function (_, value) {
        if (typeof value === 'object' && '$function' in value) {
            return new Function(value.value);
        }
        return value;
    });
    return config;
}
exports.parse = parse;
function jsonify(value) {
    Object.defineProperty(value, 'toJSON', {
        value: function () {
            return utils_1.mapValues(value, function (subValue) {
                if (utils_1.isFunction(subValue)) {
                    return stringifyFunction(subValue);
                }
                else if (typeof subValue === 'object' && !Array.isArray(subValue)) {
                    // mostly for assignments
                    return utils_1.mapValues(subValue, function (subSubValue) {
                        if (utils_1.isFunction(subSubValue)) {
                            return stringifyFunction(subSubValue);
                        }
                        return subSubValue;
                    });
                }
                return subValue;
            });
        }
    });
    return value;
}
exports.jsonify = jsonify;
