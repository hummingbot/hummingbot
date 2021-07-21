"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var util_1 = require("./util");
var useBattery = function () {
    var _a = react_1.useState({}), state = _a[0], setState = _a[1];
    var mounted = true;
    var battery = null;
    var onChange = function () {
        var charging = battery.charging, level = battery.level, chargingTime = battery.chargingTime, dischargingTime = battery.dischargingTime;
        setState({
            charging: charging,
            level: level,
            chargingTime: chargingTime,
            dischargingTime: dischargingTime,
        });
    };
    var onBattery = function () {
        onChange();
        util_1.on(battery, 'chargingchange', onChange);
        util_1.on(battery, 'levelchange', onChange);
        util_1.on(battery, 'chargingtimechange', onChange);
        util_1.on(battery, 'dischargingtimechange', onChange);
    };
    react_1.useEffect(function () {
        navigator.getBattery().then(function (bat) {
            if (mounted) {
                battery = bat;
                onBattery();
            }
        });
        return function () {
            mounted = false;
            if (battery) {
                util_1.off(battery, 'chargingchange', onChange);
                util_1.off(battery, 'levelchange', onChange);
                util_1.off(battery, 'chargingtimechange', onChange);
                util_1.off(battery, 'dischargingtimechange', onChange);
            }
        };
    }, []);
    return state;
};
exports.default = useBattery;
