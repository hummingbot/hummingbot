/**
 * @typedef {Object} ErrorOverlayOptions
 * @property {string | false} [entry] Path to a JS file that sets up the error overlay integration.
 * @property {string | false} [module] The error overlay module to use.
 * @property {string} [sockHost] The socket host to use (WDS only).
 * @property {import('type-fest').LiteralUnion<'wds' | 'whm' | 'wps' | false, string>} [sockIntegration] Path to a JS file that sets up the Webpack socket integration.
 * @property {string} [sockPath] The socket path to use (WDS only).
 * @property {number} [sockPort] The socket port to use (WDS only).
 * @property {boolean} [useLegacyWDSSockets] Uses a custom SocketJS implementation for older versions of webpack-dev-server.
 */

/**
 * @typedef {import('type-fest').SetRequired<ErrorOverlayOptions, 'entry' | 'module' | 'sockIntegration'>} NormalizedErrorOverlayOptions
 */

/**
 * @typedef {Object} ReactRefreshPluginOptions
 * @property {boolean} [disableRefreshCheck] Disables detection of react-refresh's Babel plugin (Deprecated since v0.3.0).
 * @property {string | RegExp | Array<string | RegExp>} [exclude] Files to explicitly exclude from processing.
 * @property {boolean} [forceEnable] Enables the plugin forcefully.
 * @property {string | RegExp | Array<string | RegExp>} [include] Files to explicitly include for processing.
 * @property {boolean | ErrorOverlayOptions} [overlay] Modifies how the error overlay integration works in the plugin.
 */

/**
 * @typedef {Object} OverlayOverrides
 * @property {false | NormalizedErrorOverlayOptions} overlay Modifies how the error overlay integration works in the plugin.
 */

/**
 * @typedef {import('type-fest').Merge<import('type-fest').SetRequired<import('type-fest').Except<ReactRefreshPluginOptions, 'disableRefreshCheck' | 'overlay'>, 'exclude' | 'include'>, OverlayOverrides>} NormalizedPluginOptions
 */

module.exports = {};
