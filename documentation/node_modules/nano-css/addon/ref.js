'use strict';

var addonPipe = require('./pipe').addon;

// eslint-disable-next-line no-undef
var sNano = typeof Symbol === 'object' ? Symbol('nano-css') : '@@nano-css';

exports.addon = function (renderer) {
    if (!renderer.pipe) {
        addonPipe(renderer);
    }

    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('ref', renderer, ['pipe']);
    }

    renderer.createRef = function () {
        var pipe = renderer.pipe();
        var el = null;
        var ref = function (element) {
            if (el) el = element;
            else {
                el = null;
                pipe.remove();
            }
        };
        var obj = {ref: ref};

        obj[pipe.attr] = '';

        return function (css) {
            pipe.css(css);
            return obj;
        };
    };

    renderer.ref = function (css, originalRef) {
        if (process.env.NODE_ENV !== 'production') {
            if (originalRef && typeof originalRef !== 'function') {
                console.error(
                    'nano-css "ref" function expects argument to be a ref function, "' + (typeof originalRef) + '" provided.'
                );
            }
        }

        var obj = {
            ref: function (el) {
                if (originalRef) originalRef(el);
                if (!el) return;

                var pipe = el[sNano];

                if (!pipe) {
                    el[sNano] = pipe = renderer.pipe();
                    el.setAttribute(pipe.attr, '');

                    // Add unmount logic

                    var observer = new MutationObserver(function (mutations) {
                        for (var i = 0; i < mutations.length; i++) {
                            var mutation = mutations[i];

                            if (mutation.removedNodes.length) {
                                var nodes = mutation.removedNodes;

                                for (var j = 0; j < nodes.length; j++) {
                                    if (nodes[j] === el) {
                                        pipe.remove();
                                        delete el[sNano];
                                        observer.disconnect();
                                        return;
                                    }
                                }
                            }
                        }
                    });

                    observer.observe(el.parentNode, {childList: true});
                }

                pipe.css(css);
            }
        };

        return obj;
    };
};
