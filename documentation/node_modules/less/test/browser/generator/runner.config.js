var path = require('path');
var resolve = require('resolve')

var rootFolder = path.resolve(__dirname, '../../../');
var testFolder = path.relative(rootFolder, path.dirname(resolve.sync('@less/test-data')))
var lessFolder = path.join(testFolder, 'less');

module.exports = {
    main: {
    // src is used to build list of less files to compile
        src: [
            `${lessFolder}/_main/*.less`,
            `!${lessFolder}/_main/plugin-preeval.less`, // uses ES6 syntax
            // Don't test NPM import, obviously
            `!${lessFolder}/_main/plugin-module.less`,
            `!${lessFolder}/_main/import-module.less`,
            `!${lessFolder}/_main/javascript.less`,
            `!${lessFolder}/_main/urls.less`,
            `!${lessFolder}/_main/empty.less`
        ],
        options: {
            helpers: "test/browser/runner-main-options.js",
            specs: "test/browser/runner-main-spec.js",
            outfile: "tmp/browser/test-runner-main.html"
        }
    },
    legacy: {
        src: [`${lessFolder}/legacy/*.less`],
        options: {
            helpers: "test/browser/runner-legacy-options.js",
            specs: "test/browser/runner-legacy-spec.js",
            outfile: "tmp/browser/test-runner-legacy.html"
        }
    },
    strictUnits: {
        src: [`${lessFolder}/strict-units/*.less`],
        options: {
            helpers: "test/browser/runner-strict-units-options.js",
            specs: "test/browser/runner-strict-units-spec.js",
            outfile: "tmp/browser/test-runner-strict-units.html"
        }
    },
    errors: {
        src: [
            `${lessFolder}/errors/*.less`,
            `${testFolder}/errors/javascript-error.less`,
            "test/browser/less/errors/*.less"
        ],
        options: {
            timeout: 20000,
            helpers: "test/browser/runner-errors-options.js",
            specs: "test/browser/runner-errors-spec.js",
            outfile: "tmp/browser/test-runner-errors.html"
        }
    },
    noJsErrors: {
        src: [`${lessFolder}/no-js-errors/*.less`],
        options: {
            helpers: "test/browser/runner-no-js-errors-options.js",
            specs: "test/browser/runner-no-js-errors-spec.js",
            outfile: "tmp/browser/test-runner-no-js-errors.html"
        }
    },
    browser: {
        src: [
            "test/browser/less/*.less",
            "test/browser/less/plugin/*.less"
        ],
        options: {
            helpers: "test/browser/runner-browser-options.js",
            specs: "test/browser/runner-browser-spec.js",
            outfile: "tmp/browser/test-runner-browser.html"
        }
    },
    relativeUrls: {
        src: ["test/browser/less/relative-urls/*.less"],
        options: {
            helpers: "test/browser/runner-relative-urls-options.js",
            specs: "test/browser/runner-relative-urls-spec.js",
            outfile: "tmp/browser/test-runner-relative-urls.html"
        }
    },
    rewriteUrls: {
        src: ["test/browser/less/rewrite-urls/*.less"],
        options: {
            helpers: "test/browser/runner-rewrite-urls-options.js",
            specs: "test/browser/runner-rewrite-urls-spec.js",
            outfile: "tmp/browser/test-runner-rewrite-urls.html"
        }
    },
    rootpath: {
        src: ["test/browser/less/rootpath/*.less"],
        options: {
            helpers: "test/browser/runner-rootpath-options.js",
            specs: "test/browser/runner-rootpath-spec.js",
            outfile: "tmp/browser/test-runner-rootpath.html"
        }
    },
    rootpathRelative: {
        src: ["test/browser/less/rootpath-relative/*.less"],
        options: {
            helpers: "test/browser/runner-rootpath-relative-options.js",
            specs: "test/browser/runner-rootpath-relative-spec.js",
            outfile: "tmp/browser/test-runner-rootpath-relative.html"
        }
    },
    rootpathRewriteUrls: {
        src: ["test/browser/less/rootpath-rewrite-urls/*.less"],
        options: {
            helpers:
            "test/browser/runner-rootpath-rewrite-urls-options.js",
            specs: "test/browser/runner-rootpath-rewrite-urls-spec.js",
            outfile:
            "tmp/browser/test-runner-rootpath-rewrite-urls.html"
        }
    },
    production: {
        src: ["test/browser/less/production/*.less"],
        options: {
            helpers: "test/browser/runner-production-options.js",
            specs: "test/browser/runner-production-spec.js",
            outfile: "tmp/browser/test-runner-production.html"
        }
    },
    modifyVars: {
        src: ["test/browser/less/modify-vars/*.less"],
        options: {
            helpers: "test/browser/runner-modify-vars-options.js",
            specs: "test/browser/runner-modify-vars-spec.js",
            outfile: "tmp/browser/test-runner-modify-vars.html"
        }
    },
    globalVars: {
        src: ["test/browser/less/global-vars/*.less"],
        options: {
            helpers: "test/browser/runner-global-vars-options.js",
            specs: "test/browser/runner-global-vars-spec.js",
            outfile: "tmp/browser/test-runner-global-vars.html"
        }
    },
    postProcessorPlugin: {
        src: [`${lessFolder}/postProcessorPlugin/*.less`],
        options: {
            helpers: [
                `test/plugins/postprocess/index.js`,
                "test/browser/runner-postProcessorPlugin-options.js"
            ],
            specs: "test/browser/runner-postProcessorPlugin.js",
            outfile:
            "tmp/browser/test-runner-post-processor-plugin.html"
        }
    },
    preProcessorPlugin: {
        src: [`${lessFolder}/preProcessorPlugin/*.less`],
        options: {
            helpers: [
                `test/plugins/preprocess/index.js`,
                "test/browser/runner-preProcessorPlugin-options.js"
            ],
            specs: "test/browser/runner-preProcessorPlugin.js",
            outfile: "tmp/browser/test-runner-pre-processor-plugin.html"
        }
    },
    visitorPlugin: {
        src: [`${lessFolder}/visitorPlugin/*.less`],
        options: {
            helpers: [
                `test/plugins/visitor/index.js`,
                "test/browser/runner-VisitorPlugin-options.js"
            ],
            specs: "test/browser/runner-VisitorPlugin.js",
            outfile: "tmp/browser/test-runner-visitor-plugin.html"
        }
    },
    filemanagerPlugin: {
        src: [`${lessFolder}/filemanagerPlugin/*.less`],
        options: {
            helpers: [
                `test/plugins/filemanager/index.js`,
                "test/browser/runner-filemanagerPlugin-options.js"
            ],
            specs: "test/browser/runner-filemanagerPlugin.js",
            outfile: "tmp/browser/test-runner-filemanager-plugin.html"
        }
    }
}