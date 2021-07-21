'use strict';

exports.addon = function (renderer) {
    if (renderer.client) {
        console.error(
            'You are running nano-css "extract" addon in browser. ' +
            'You should use it ONLY on server and ONLY at build time.'
        );

        return;
    }

    var sheet = renderer.sheet;

    // eslint-disable-next-line no-unused-vars
    var dummy;

    // Evaluate all lazy-evaluated sheet() styles.
    if (sheet) {
        renderer.sheet = function (map) {
            var styles = sheet.apply(this, arguments);

            for (var name in map) dummy = styles[name];

            return styles;
        };
    }

    var jsx = renderer.jsx;

    // Render jsx component once to extract its static CSS.
    if (jsx) {
        renderer.jsx = function () {
            var jsxComponent = jsx.apply(this, arguments);

            process.nextTick(function () {
                jsxComponent(jsxComponent.defaultProps || {});
            });

            return jsxComponent;
        };
    }

    var style = renderer.style;

    // Render styled component once with default props
    // to extract its static CSS and "default" dynamic CSS.
    if (style) {
        renderer.style = function () {
            var styledComponent = style.apply(this, arguments);

            process.nextTick(function () {
                styledComponent(styledComponent.defaultProps || {});
            });

            return styledComponent;
        };
    }
};
