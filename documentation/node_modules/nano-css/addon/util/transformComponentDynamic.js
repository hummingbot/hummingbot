'use strict';

module.exports = function (renderer, Comp, dynamicTemplate) {
    if (process.env.NODE_ENV !== 'production') {
        if (typeof dynamicTemplate !== 'function') {
            var what;

            try {
                what = JSON.stringify(dynamicTemplate);
            } catch (error) {
                what = String(dynamicTemplate);
            }

            throw new TypeError('Dynamic CSS template must always be a function, ' + 'received: ' + what);
        }
    }

    var prototype = Comp.prototype;
    var render_ = prototype.render;

    prototype.render = function () {
        var element = render_.apply(this, arguments);
        var props = element.props;
        var dynamicClassName = '';

        if (dynamicTemplate) {
            var dynamicStyles = dynamicTemplate(this.props);

            if (dynamicStyles) {
                dynamicClassName = renderer.cache(dynamicStyles);
            }
        }

        if (!dynamicClassName) {
            return element;
        }

        var className = (props.className || '') + dynamicClassName;

        if (process.env.NODE_ENV !== 'production') {
            return require('react').cloneElement(element, Object.assign({}, props, {
                className: className
            }), props.children);
        }

        props.className = className;

        return element;
    };
};
