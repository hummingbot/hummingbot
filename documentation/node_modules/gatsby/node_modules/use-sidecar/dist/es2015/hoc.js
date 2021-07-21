import * as tslib_1 from "tslib";
import * as React from 'react';
import { useSidecar } from "./hook";
export function sidecar(importer, errorComponent) {
    var ErrorCase = function () { return errorComponent; };
    return function Sidecar(props) {
        var _a = useSidecar(importer, props.sideCar), Car = _a[0], error = _a[1];
        if (error && errorComponent) {
            return ErrorCase;
        }
        return Car ? React.createElement(Car, tslib_1.__assign({}, props)) : null;
    };
}
