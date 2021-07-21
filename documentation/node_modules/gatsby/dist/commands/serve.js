"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

var _path = _interopRequireDefault(require("path"));

var _betterOpn = _interopRequireDefault(require("better-opn"));

var _fsExtra = _interopRequireDefault(require("fs-extra"));

var _compression = _interopRequireDefault(require("compression"));

var _express = _interopRequireDefault(require("express"));

var _chalk = _interopRequireDefault(require("chalk"));

var _utils = require("@reach/router/lib/utils");

var _signalExit = _interopRequireDefault(require("signal-exit"));

var _reporter = _interopRequireDefault(require("gatsby-cli/lib/reporter"));

var _gatsbyTelemetry = _interopRequireDefault(require("gatsby-telemetry"));

var _detectPortInUseAndPrompt = require("../utils/detect-port-in-use-and-prompt");

var _getConfigFile = require("../bootstrap/get-config-file");

var _preferDefault = require("../bootstrap/prefer-default");

var _prepareUrls = require("../utils/prepare-urls");

(0, _signalExit.default)(() => {
  _gatsbyTelemetry.default.trackCli(`SERVE_STOP`);
});

const readMatchPaths = async (program) => {
  const filePath = _path.default.join(program.directory, `.cache`, `match-paths.json`);

  let rawJSON = `[]`;

  try {
    rawJSON = await _fsExtra.default.readFile(filePath, `utf8`);
  } catch (error) {
    _reporter.default.warn(error);

    _reporter.default.warn(`Could not read ${_chalk.default.bold(`match-paths.json`)} from the .cache directory`);

    _reporter.default.warn(`Client-side routing will not work correctly. Maybe you need to re-run ${_chalk.default.bold(`gatsby build`)}?`);
  }

  return JSON.parse(rawJSON);
};

const matchPathRouter = (matchPaths, options) => (req, res, next) => {
  const {
    url
  } = req;

  if (req.accepts(`html`)) {
    const matchPath = matchPaths.find(({
      matchPath
    }) => (0, _utils.match)(matchPath, url) !== null);

    if (matchPath) {
      return res.sendFile(_path.default.join(matchPath.path, `index.html`), options, err => {
        if (err) {
          next();
        }
      });
    }
  }

  return next();
};

module.exports = async program => {
  _gatsbyTelemetry.default.trackCli(`SERVE_START`);

  _gatsbyTelemetry.default.startBackgroundUpdate();

  let {
    prefixPaths,
    port,
    open,
    host
  } = program;
  port = typeof port === `string` ? parseInt(port, 10) : port;
  const {
    configModule
  } = await (0, _getConfigFile.getConfigFile)(program.directory, `gatsby-config`);
  const config = (0, _preferDefault.preferDefault)(configModule);
  const {
    pathPrefix: configPathPrefix
  } = config || {};
  const pathPrefix = prefixPaths && configPathPrefix ? configPathPrefix : `/`;

  const root = _path.default.join(program.directory, `public`);

  const app = (0, _express.default)();

  const router = _express.default.Router();

  app.use(_gatsbyTelemetry.default.expressMiddleware(`SERVE`));
  router.use((0, _compression.default)());
  router.use(_express.default.static(`public`, {
    dotfiles: `allow`
  }));
  const matchPaths = await readMatchPaths(program);
  router.use(matchPathRouter(matchPaths, {
    root
  }));
  router.use((req, res, next) => {
    if (req.accepts(`html`)) {
      return res.status(404).sendFile(`404.html`, {
        root
      });
    }

    return next();
  });
  app.use(function (_, res, next) {
    res.header(`Access-Control-Allow-Origin`, `*`);
    res.header(`Access-Control-Allow-Headers`, `Origin, X-Requested-With, Content-Type, Accept`);
    next();
  });
  app.use(pathPrefix, router);

  function printInstructions(appName, urls) {
    console.log();
    console.log(`You can now view ${_chalk.default.bold(appName)} in the browser.`);
    console.log();

    if (urls.lanUrlForTerminal) {
      console.log(`  ${_chalk.default.bold(`Local:`)}            ${urls.localUrlForTerminal}`);
      console.log(`  ${_chalk.default.bold(`On Your Network:`)}  ${urls.lanUrlForTerminal}`);
    } else {
      console.log(`  ${urls.localUrlForTerminal}`);
    }
  }

  const startListening = () => {
    app.listen(port, host, () => {
      const urls = (0, _prepareUrls.prepareUrls)(program.ssl ? `https` : `http`, program.host, port);
      printInstructions(program.sitePackageJson.name || `(Unnamed package)`, urls);

      if (open) {
        _reporter.default.info(`Opening browser...`);

        Promise.resolve((0, _betterOpn.default)(urls.localUrlForBrowser)).catch(() => _reporter.default.warn(`Browser not opened because no browser was found`));
      }
    });
  };

  try {
    port = await (0, _detectPortInUseAndPrompt.detectPortInUseAndPrompt)(port);
    startListening();
  } catch (e) {
    if (e.message === `USER_REJECTED`) {
      return;
    }

    throw e;
  }
};
//# sourceMappingURL=serve.js.map