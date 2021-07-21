/**
 * Validated the preload object
 * @param {Object | boolean} preload configuration object or boolean passed via the options parameter to axe.run
 * @return {boolean}
 * @private
 */
function isValidPreloadObject(preload) {
	return typeof preload === 'object' && Array.isArray(preload.assets);
}

/**
 * Returns a boolean which decides if preload is configured
 * @param {Object} options run configuration options (or defaults) passed via axe.run
 * @return {boolean} defaults to true
 */
axe.utils.shouldPreload = function shouldPreload(options) {
	if (!options || options.preload === undefined || options.preload === null) {
		return true; // by default `preload` requested assets eg: ['cssom']
	}
	if (typeof options.preload === 'boolean') {
		return options.preload;
	}
	return isValidPreloadObject(options.preload);
};

/**
 * Constructs a configuration object representing the preload requested assets & timeout
 * @param {Object} options run configuration options (or defaults) passed via axe.run
 * @return {Object} configuration
 */
axe.utils.getPreloadConfig = function getPreloadConfig(options) {
	const { assets, timeout } = axe.constants.preload;
	const config = {
		assets,
		timeout
	};

	// if no `preload` is configured via `options` - return default config
	if (!options.preload) {
		return config;
	}

	// if type is boolean
	if (typeof options.preload === 'boolean') {
		return config;
	}

	// check if requested assets to preload are valid items
	const areRequestedAssetsValid = options.preload.assets.every(a =>
		assets.includes(a.toLowerCase())
	);

	if (!areRequestedAssetsValid) {
		throw new Error(
			`Requested assets, not supported. ` +
				`Supported assets are: ${assets.join(', ')}.`
		);
	}

	// unique assets to load, in case user had requested same asset type many times.
	config.assets = axe.utils.uniqueArray(
		options.preload.assets.map(a => a.toLowerCase()),
		[]
	);

	if (
		options.preload.timeout &&
		typeof options.preload.timeout === 'number' &&
		!isNaN(options.preload.timeout)
	) {
		config.timeout = options.preload.timeout;
	}
	return config;
};

/**
 * Returns a Promise with results of all requested preload(able) assets. eg: ['cssom'].
 *
 * @param {Object} options run configuration options (or defaults) passed via axe.run
 * @return {Object} Promise
 */
axe.utils.preload = function preload(options) {
	const preloadFunctionsMap = {
		cssom: axe.utils.preloadCssom,
		media: axe.utils.preloadMedia
	};

	const shouldPreload = axe.utils.shouldPreload(options);
	if (!shouldPreload) {
		return Promise.resolve();
	}

	return new Promise((resolve, reject) => {
		const { assets, timeout } = axe.utils.getPreloadConfig(options);

		/**
		 * Start `timeout` timer for preloading assets
		 * -> reject if allowed time expires.
		 */
		const preloadTimeout = setTimeout(
			() => reject(new Error(`Preload assets timed out.`)),
			timeout
		);

		/**
		 * Fetch requested `assets`
		 */
		Promise.all(
			assets.map(asset =>
				preloadFunctionsMap[asset](options).then(results => {
					return {
						[asset]: results
					};
				})
			)
		)
			.then(results => {
				/**
				 * Combine array of results into an object map
				 *
				 * From ->
				 * 	[{cssom: [...], aom: [...]}]
				 * To ->
				 * 	{
				 * 		cssom: [...]
				 * 	 	aom: [...]
				 * 	}
				 */
				const preloadAssets = results.reduce((out, result) => {
					return {
						...out,
						...result
					};
				}, {});

				clearTimeout(preloadTimeout);
				resolve(preloadAssets);
			})
			.catch(err => {
				clearTimeout(preloadTimeout);
				reject(err);
			});
	});
};
