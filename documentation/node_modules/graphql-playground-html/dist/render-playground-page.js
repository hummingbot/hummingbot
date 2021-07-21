"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
Object.defineProperty(exports, "__esModule", { value: true });
var xss_1 = require("xss");
var get_loading_markup_1 = require("./get-loading-markup");
var filter = function (val) {
    return xss_1.filterXSS(val, {
        // @ts-ignore
        whiteList: [],
        stripIgnoreTag: true,
        stripIgnoreTagBody: ["script"]
    });
};
var loading = get_loading_markup_1.default();
var CONFIG_ID = 'playground-config';
var getCdnMarkup = function (_a) {
    var version = _a.version, _b = _a.cdnUrl, cdnUrl = _b === void 0 ? '//cdn.jsdelivr.net/npm' : _b, faviconUrl = _a.faviconUrl;
    var buildCDNUrl = function (packageName, suffix) { return filter(cdnUrl + "/" + packageName + (version ? "@" + version : '') + "/" + suffix || ''); };
    return "\n    <link \n      rel=\"stylesheet\" \n      href=\"" + buildCDNUrl('graphql-playground-react', 'build/static/css/index.css') + "\"\n    />\n    " + (typeof faviconUrl === 'string' ? "<link rel=\"shortcut icon\" href=\"" + filter(faviconUrl || '') + "\" />" : '') + "\n    " + (faviconUrl === undefined ? "<link rel=\"shortcut icon\" href=\"" + buildCDNUrl('graphql-playground-react', 'build/favicon.png') + "\" />" : '') + "\n    <script \n      src=\"" + buildCDNUrl('graphql-playground-react', 'build/static/js/middleware.js') + "\"\n    ></script>\n";
};
var renderConfig = function (config) {
    return xss_1.filterXSS("<div id=\"" + CONFIG_ID + "\">" + JSON.stringify(config) + "</div>", {
        whiteList: { div: ['id'] },
    });
};
function renderPlaygroundPage(options) {
    var extendedOptions = __assign(__assign({}, options), { canSaveConfig: false });
    // for compatibility
    if (options.subscriptionsEndpoint) {
        extendedOptions.subscriptionEndpoint = filter(options.subscriptionsEndpoint || '');
    }
    if (options.config) {
        extendedOptions.configString = JSON.stringify(options.config, null, 2);
    }
    if (!extendedOptions.endpoint && !extendedOptions.configString) {
        /* tslint:disable-next-line */
        console.warn("WARNING: You didn't provide an endpoint and don't have a .graphqlconfig. Make sure you have at least one of them.");
    }
    else if (extendedOptions.endpoint) {
        extendedOptions.endpoint = filter(extendedOptions.endpoint || '');
    }
    return "\n  <!DOCTYPE html>\n  <html>\n  <head>\n    <meta charset=utf-8 />\n    <meta name=\"viewport\" content=\"user-scalable=no, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, minimal-ui\">\n    <link href=\"https://fonts.googleapis.com/css?family=Open+Sans:300,400,600,700|Source+Code+Pro:400,700\" rel=\"stylesheet\">\n    <title>" + (extendedOptions.title || 'GraphQL Playground') + "</title>\n    " + (extendedOptions.env === 'react' || extendedOptions.env === 'electron'
        ? ''
        : getCdnMarkup(extendedOptions)) + "\n  </head>\n  <body>\n    <style type=\"text/css\">\n      html {\n        font-family: \"Open Sans\", sans-serif;\n        overflow: hidden;\n      }\n  \n      body {\n        margin: 0;\n        background: #172a3a;\n      }\n\n      #" + CONFIG_ID + " {\n        display: none;\n      }\n  \n      .playgroundIn {\n        -webkit-animation: playgroundIn 0.5s ease-out forwards;\n        animation: playgroundIn 0.5s ease-out forwards;\n      }\n  \n      @-webkit-keyframes playgroundIn {\n        from {\n          opacity: 0;\n          -webkit-transform: translateY(10px);\n          -ms-transform: translateY(10px);\n          transform: translateY(10px);\n        }\n        to {\n          opacity: 1;\n          -webkit-transform: translateY(0);\n          -ms-transform: translateY(0);\n          transform: translateY(0);\n        }\n      }\n  \n      @keyframes playgroundIn {\n        from {\n          opacity: 0;\n          -webkit-transform: translateY(10px);\n          -ms-transform: translateY(10px);\n          transform: translateY(10px);\n        }\n        to {\n          opacity: 1;\n          -webkit-transform: translateY(0);\n          -ms-transform: translateY(0);\n          transform: translateY(0);\n        }\n      }\n    </style>\n    " + loading.container + "\n    " + renderConfig(extendedOptions) + "\n    <div id=\"root\" />\n    <script type=\"text/javascript\">\n      window.addEventListener('load', function (event) {\n        " + loading.script + "\n  \n        const root = document.getElementById('root');\n        root.classList.add('playgroundIn');\n        const configText = document.getElementById('" + CONFIG_ID + "').innerText;\n        \n        if(configText && configText.length) {\n          try {\n            GraphQLPlayground.init(root, JSON.parse(configText));\n          }\n          catch(err) {\n            console.error(\"could not find config\")\n          }\n        }\n        else {\n          GraphQLPlayground.init(root);\n        }\n      })\n    </script>\n  </body>\n  </html>\n";
}
exports.renderPlaygroundPage = renderPlaygroundPage;
//# sourceMappingURL=render-playground-page.js.map