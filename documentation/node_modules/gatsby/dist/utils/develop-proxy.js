"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.startDevelopProxy = void 0;

var _http = _interopRequireDefault(require("http"));

var _https = _interopRequireDefault(require("https"));

var _httpProxy = _interopRequireDefault(require("http-proxy"));

var _path = _interopRequireDefault(require("path"));

var _fsExtra = _interopRequireDefault(require("fs-extra"));

var _gatsbyCoreUtils = require("gatsby-core-utils");

var _st = _interopRequireDefault(require("st"));

var _restartingScreen = _interopRequireDefault(require("./restarting-screen"));

const noop = () => {};

const adminFolder = _path.default.join(__dirname, `..`, `..`, `gatsby-admin-public`);

const serveAdmin = (0, _st.default)({
  path: adminFolder,
  url: `/___admin`,
  index: `index.html`
});

const startDevelopProxy = input => {
  let shouldServeRestartingScreen = false;

  const proxy = _httpProxy.default.createProxyServer({
    target: `http://localhost:${input.targetPort}`,
    changeOrigin: true,
    preserveHeaderKeyCase: true,
    autoRewrite: true,
    ws: true
  }); // Noop on proxy errors, as this throws a bunch of "Socket hang up"
  // ones whenever the page is refreshed


  proxy.on(`error`, noop);

  const app = (req, res) => {
    if (process.env.GATSBY_EXPERIMENTAL_ENABLE_ADMIN) {
      const wasAdminRequest = serveAdmin(req, res);

      if (wasAdminRequest) {
        return;
      }
    } // Add a route at localhost:8000/___services for service discovery


    if (req.url === `/___services`) {
      (0, _gatsbyCoreUtils.getServices)(input.program.directory).then(services => {
        res.setHeader(`Content-Type`, `application/json`);
        res.end(JSON.stringify(services));
      });
      return;
    }

    if (req.url === `/socket.io/socket.io.js`) {
      res.setHeader(`Content-Type`, `application/javascript`);
      res.end(_fsExtra.default.readFileSync(require.resolve(`socket.io-client/dist/socket.io.js`)));
      return;
    }

    if (shouldServeRestartingScreen || req.url === `/___debug-restarting-screen`) {
      res.end(_restartingScreen.default);
      return;
    }

    proxy.web(req, res);
  };

  const server = input.program.ssl ? _https.default.createServer(input.program.ssl, app) : _http.default.createServer(app);
  server.on(`upgrade`, function (req, socket, head) {
    proxy.ws(req, socket, head);
  });
  server.listen(input.proxyPort, input.program.host);
  return {
    server,
    serveRestartingScreen: () => {
      shouldServeRestartingScreen = true;
    },
    serveSite: () => {
      shouldServeRestartingScreen = false;
    }
  };
};

exports.startDevelopProxy = startDevelopProxy;
//# sourceMappingURL=develop-proxy.js.map