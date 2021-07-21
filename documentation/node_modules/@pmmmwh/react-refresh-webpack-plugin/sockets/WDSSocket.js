/* global __webpack_dev_server_client__ */

const url = require('native-url');
const getSocketUrlParts = require('./utils/getSocketUrlParts');

/**
 * Initializes a socket server for HMR for webpack-dev-server.
 * @param {function(*): void} messageHandler A handler to consume Webpack compilation messages.
 * @param {string} [resourceQuery] Webpack's `__resourceQuery` string.
 * @returns {void}
 */
function initWDSSocket(messageHandler, resourceQuery) {
  if (typeof __webpack_dev_server_client__ !== 'undefined') {
    const SocketClient = __webpack_dev_server_client__;

    const urlParts = getSocketUrlParts(resourceQuery);
    const connection = new SocketClient(url.format(urlParts));

    connection.onMessage(function onSocketMessage(data) {
      const message = JSON.parse(data);
      messageHandler(message);
    });
  }
}

module.exports = initWDSSocket;
