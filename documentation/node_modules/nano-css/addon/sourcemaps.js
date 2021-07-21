'use strict';

var StackTrace = require('stacktrace-js');
var SourcemapCodec = require('sourcemap-codec');

function findStackframe (frames) {
    for (var i = 4; i < frames.length; i++) {
        if (!frames[i].fileName.match(/addon\/[^.]+\.js/)) {
            return frames[i];
        }
    }
}

exports.addon = function (renderer) {
    if (process.env.NODE_ENV === 'production') {
        // eslint-disable-next-line no-console
        console.log(
            'nano-css sourcemaps addon should be installed only in development mode. ' +
            'Use (process.env.NODE !== "production") to check if you are in development mode.'
        );

        return;
    }

    var queue = [];
    var timeout = null;
    var sourceCache = {};

    function flush () {
        timeout = null;

        var sources = [];
        var segments = [];
        var rules = [];

        for (var i = 0; i < queue.length; i++) {
            var item = queue[i];

            rules.push(item.rule);
            segments.push([[0, sources.length, item.lineNumber - 1, 0]]);
            sources.push(item.fileName);
        }

        queue = [];

        var mappings = SourcemapCodec.encode(segments);
        var map = {
            version: 3,
            sources: sources,
            mappings: mappings,
            sourcesContent: sources.map(function (source) {
                return sourceCache[source];
            }),
        };

        var json = JSON.stringify(map);
        var base64 = window.btoa(json);
        var css = rules.join('\n') + '\n/*# sourceMappingURL=data:application/json;charset=utf-8;base64,' + base64 + ' */';
        var style = document.createElement('style');

        style.setAttribute('data-nano-css-sourcemaps', '');
        style.appendChild(document.createTextNode(css));
        document.head.appendChild(style);
    }

    function enqueue (rawCss) {
        StackTrace.get({sourceCache: sourceCache})
            .then(function (stackframes) {
                var frame = findStackframe(stackframes);

                if (!frame) {
                    return;
                }

                queue.push({
                    rule: rawCss,
                    fileName: frame.fileName,
                    lineNumber: frame.lineNumber,
                });

                if (!timeout) {
                    timeout = setTimeout(flush, 100);
                }
            // eslint-disable-next-line no-console
            }, console.log);
    }

    var putRaw = renderer.putRaw;

    renderer.putRaw = function (rawCSS) {
        enqueue(rawCSS);
        putRaw.apply(null, arguments);
    };

    renderer.sourcemaps = true;
};
