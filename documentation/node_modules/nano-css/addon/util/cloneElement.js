'use strict';

module.exports = function (renderer, element, props) {
    var newProps = renderer.assign({}, element.props, props);

    if (element.ref) {
        newProps.ref = element.ref;
    }

    return renderer.h(element.type, newProps);
};
