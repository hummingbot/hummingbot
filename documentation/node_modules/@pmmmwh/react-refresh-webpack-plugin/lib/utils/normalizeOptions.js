/**
 * Sets a constant default value for the property when it is undefined.
 * @template T
 * @template {keyof T} Property
 * @param {T} object An object.
 * @param {Property} property A property of the provided object.
 * @param {T[Property]} defaultValue The default value to set for the property.
 * @returns {T[Property]} The defaulted property value.
 */
const d = (object, property, defaultValue) => {
  if (typeof object[property] === 'undefined' && typeof defaultValue !== 'undefined') {
    object[property] = defaultValue;
  }
  return object[property];
};

/**
 * Resolves the value for a nested object option.
 * @template T
 * @template {keyof T} Property
 * @template Result
 * @param {T} object An object.
 * @param {Property} property A property of the provided object.
 * @param {function(T | undefined): Result} fn The handler to resolve the property's value.
 * @returns {Result} The resolved option value.
 */
const nestedOption = (object, property, fn) => {
  object[property] = fn(object[property]);
  return object[property];
};

/**
 * Normalizes the options for the plugin.
 * @param {import('../types').ReactRefreshPluginOptions} options Non-normalized plugin options.
 * @returns {import('../types').NormalizedPluginOptions} Normalized plugin options.
 */
const normalizeOptions = (options) => {
  // Show deprecation notice for the `disableRefreshCheck` option and remove it
  if (typeof options.disableRefreshCheck !== 'undefined') {
    delete options.disableRefreshCheck;
    console.warn(
      [
        'The "disableRefreshCheck" option has been deprecated and will not have any effect on how the plugin parses files.',
        'Please remove it from your configuration.',
      ].join(' ')
    );
  }

  d(options, 'exclude', /node_modules/i);
  d(options, 'include', /\.([jt]sx?|flow)$/i);
  d(options, 'forceEnable');

  nestedOption(options, 'overlay', (overlay) => {
    /** @type {import('../types').NormalizedErrorOverlayOptions} */
    const defaults = {
      entry: require.resolve('../../client/ErrorOverlayEntry'),
      module: require.resolve('../../overlay'),
      sockIntegration: 'wds',
    };

    if (overlay === false) {
      return false;
    }
    if (typeof overlay === 'undefined' || overlay === true) {
      return defaults;
    }

    d(overlay, 'entry', defaults.entry);
    d(overlay, 'module', defaults.module);
    d(overlay, 'sockIntegration', defaults.sockIntegration);
    d(overlay, 'sockHost');
    d(overlay, 'sockPath');
    d(overlay, 'sockPort');
    d(options, 'useLegacyWDSSockets');

    return overlay;
  });

  return options;
};

module.exports = normalizeOptions;
