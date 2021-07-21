'use strict';

var transformComponentStatic = require('./util/transformComponentStatic');
var transformComponentDynamic = require('./util/transformComponentDynamic');

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('css', renderer, ['rule', 'cache']);
    }

    renderer.css = function (a, b) {
        var isComponent = a && a.prototype && a.prototype.render;

        // Static class decorator.
        if (isComponent) {
            if (a.css) transformComponentStatic(renderer, a.prototype, a.css);

            var componentWillMount_ = a.prototype.componentWillMount;

            a.prototype.componentWillMount = function () {
                if (this.css) transformComponentDynamic(renderer, a, this.css.bind(this));
                if (componentWillMount_) componentWillMount_.apply(this);
            };

            return a;
        }

        return function (instanceOrComp, key, descriptor) {
            if (typeof key === 'string') {
                // .render() method decorator
                var Comp = instanceOrComp.constructor;

                transformComponentDynamic(renderer, Comp, a);
                descriptor.value = Comp.prototype.render;

                return descriptor;
            }

            // Class decorator
            transformComponentStatic(renderer, instanceOrComp.prototype, a, b);
        };
    };
};
