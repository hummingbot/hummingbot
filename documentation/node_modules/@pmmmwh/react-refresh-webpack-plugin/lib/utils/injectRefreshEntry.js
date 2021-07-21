const querystring = require('querystring');
const createError = require('./createError');

/** @typedef {string | string[] | import('webpack').Entry} StaticEntry */
/** @typedef {StaticEntry | import('webpack').EntryFunc} WebpackEntry */

/**
 * Checks if a Webpack entry string is related to socket integrations.
 * @param {string} entry A Webpack entry string.
 * @returns {boolean} Whether the entry is related to socket integrations.
 */
function isSocketEntry(entry) {
  /**
   * Webpack entries related to socket integrations.
   * They have to run before any code that sets up the error overlay.
   * @type {string[]}
   */
  const socketEntries = [
    'webpack-dev-server/client',
    'webpack-hot-middleware/client',
    'webpack-plugin-serve/client',
    'react-dev-utils/webpackHotDevClient',
  ];

  return socketEntries.some((socketEntry) => entry.includes(socketEntry));
}

/**
 * Injects an entry to the bundle for react-refresh.
 * @param {WebpackEntry} [originalEntry] A Webpack entry object.
 * @param {import('../types').NormalizedPluginOptions} options Configuration options for this plugin.
 * @returns {WebpackEntry} An injected entry object.
 */
function injectRefreshEntry(originalEntry, options) {
  /** @type {Record<string, *>} */
  let resourceQuery = {};
  if (options.overlay) {
    options.overlay.sockHost && (resourceQuery.sockHost = options.overlay.sockHost);
    options.overlay.sockPath && (resourceQuery.sockPath = options.overlay.sockPath);
    options.overlay.sockPort && (resourceQuery.sockPort = options.overlay.sockPort);
  }

  // We don't need to URI encode the resourceQuery as it will be parsed by Webpack
  const queryString = querystring.stringify(resourceQuery, undefined, undefined, {
    /**
     * @param {string} string
     * @returns {string}
     */
    encodeURIComponent(string) {
      return string;
    },
  });

  const prependEntries = [
    // React-refresh runtime
    require.resolve('../../client/ReactRefreshEntry'),
  ];

  const overlayEntries = [
    // Legacy WDS SockJS integration
    options.overlay &&
      options.overlay.useLegacyWDSSockets &&
      require.resolve('../../client/LegacyWDSSocketEntry'),
    // Error overlay runtime
    options.overlay &&
      options.overlay.entry &&
      options.overlay.entry + (queryString && `?${queryString}`),
  ].filter(Boolean);

  // Single string entry point
  if (typeof originalEntry === 'string') {
    if (isSocketEntry(originalEntry)) {
      return [...prependEntries, originalEntry, ...overlayEntries];
    }

    return [...prependEntries, ...overlayEntries, originalEntry];
  }
  // Single array entry point
  if (Array.isArray(originalEntry)) {
    const socketEntryIndex = originalEntry.findIndex(isSocketEntry);

    let socketAndPrecedingEntries = [];
    if (socketEntryIndex !== -1) {
      socketAndPrecedingEntries = originalEntry.splice(0, socketEntryIndex + 1);
    }

    return [...prependEntries, ...socketAndPrecedingEntries, ...overlayEntries, ...originalEntry];
  }
  // Multiple entry points
  if (typeof originalEntry === 'object') {
    return Object.entries(originalEntry).reduce(
      (acc, [curKey, curEntry]) => ({
        ...acc,
        [curKey]:
          typeof curEntry === 'object' && curEntry.import
            ? {
                ...curEntry,
                import: injectRefreshEntry(curEntry.import, options),
              }
            : injectRefreshEntry(curEntry, options),
      }),
      {}
    );
  }
  // Dynamic entry points
  if (typeof originalEntry === 'function') {
    return (...args) =>
      Promise.resolve(originalEntry(...args)).then((resolvedEntry) =>
        injectRefreshEntry(resolvedEntry, options)
      );
  }

  throw createError('Failed to parse the Webpack `entry` object!');
}

module.exports = injectRefreshEntry;
