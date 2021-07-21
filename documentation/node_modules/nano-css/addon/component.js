'use strict';

var React = require('react');
var Component = React.Component;
var transformComponentStatic = require('./util/transformComponentStatic');
var transformComponentDynamic = require('./util/transformComponentDynamic');

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('component', renderer, ['rule', 'cache']);
    }

    function CssComponent (props, context) {
        Component.call(this, props, context);

        var Comp = this.constructor;

        if (Comp.css) transformComponentStatic(renderer, Comp.prototype, Comp.css);
        if (this.css) transformComponentDynamic(renderer, Comp, this.css.bind(this));
    }

    CssComponent.prototype = Object.create(Component.prototype);
    CssComponent.prototype.constructor = CssComponent;

    renderer.Component = CssComponent;
};
