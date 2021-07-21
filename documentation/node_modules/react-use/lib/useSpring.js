"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var react_1 = require("react");
var rebound_1 = require("rebound");
var useSpring = function (targetValue, tension, friction) {
    if (targetValue === void 0) { targetValue = 0; }
    if (tension === void 0) { tension = 50; }
    if (friction === void 0) { friction = 3; }
    var _a = react_1.useState(null), spring = _a[0], setSpring = _a[1];
    var _b = react_1.useState(targetValue), value = _b[0], setValue = _b[1];
    react_1.useEffect(function () {
        var listener = {
            onSpringUpdate: function (currentSpring) {
                var newValue = currentSpring.getCurrentValue();
                setValue(newValue);
            },
        };
        if (!spring) {
            var newSpring = new rebound_1.SpringSystem().createSpring(tension, friction);
            newSpring.setCurrentValue(targetValue);
            setSpring(newSpring);
            newSpring.addListener(listener);
            return;
        }
        return function () {
            spring.removeListener(listener);
            setSpring(null);
        };
    }, [tension, friction]);
    react_1.useEffect(function () {
        if (spring) {
            spring.setEndValue(targetValue);
        }
    }, [targetValue]);
    return value;
};
exports.default = useSpring;
