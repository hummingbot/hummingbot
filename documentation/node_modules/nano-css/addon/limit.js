'use strict';

exports.addon = function (renderer, limit) {
    limit = limit || 50000;

    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('limit', renderer, ['putRaw']);
    }

    if (!renderer.client) {
        var putRaw = renderer.putRaw;

        renderer.putRaw = function (rawCssRule) {
            if (renderer.raw.length + rawCssRule.length > limit) {
                /* eslint-disable */
                console.info('CSS was not injected, because total CSS would go over ' + limit + ' byte limit.');
                console.log(rawCssRule);
                /* eslint-enable */

                return;
            }

            putRaw(rawCssRule);
        };
    }
};
