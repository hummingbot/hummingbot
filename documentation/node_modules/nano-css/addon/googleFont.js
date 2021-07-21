'use strict';

function createUrl (font, weights, subsets) {
    var params = '?family=' + encodeURIComponent(font);

    if (weights) {
        if (!(weights instanceof Array))
            weights = [weights];

        params += ':' + weights.join(',');
    }

    if (subsets) {
        if (!(subsets instanceof Array))
            subsets = [subsets];

        params += '&subset=' + subsets.join(',');
    }

    return 'https://fonts.googleapis.com/css' + params;
}

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('hydrate', renderer, ['put']);
    }

    if (renderer.client) {
        renderer.googleFont = function (font, weights, subsets) {
            var el = document.createElement('link');

            el.href = createUrl(font, weights, subsets);
            el.rel = 'stylesheet';
            el.type = 'text/css';

            document.head.appendChild(el);
        };
    } else {
        renderer.googleFont = function (font, weights, subsets) {
            renderer.putRaw("@import url('" + createUrl(font, weights, subsets) + "');");
        };
    }
};
