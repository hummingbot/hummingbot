/* global __react_refresh_error_overlay__, __react_refresh_test__, __react_refresh_utils__, __webpack_require__ */

/**
 * Code appended to each JS-like module for react-refresh capabilities.
 *
 * `__react_refresh_utils__` will be replaced with actual utils during source parsing by `webpack.ProvidePlugin`.
 *
 * The function declaration syntax below is needed for `Template.getFunctionContent` to parse this.
 *
 * [Reference for Runtime Injection](https://github.com/webpack/webpack/blob/b07d3b67d2252f08e4bb65d354a11c9b69f8b434/lib/HotModuleReplacementPlugin.js#L419)
 * [Reference for HMR Error Recovery](https://github.com/webpack/webpack/issues/418#issuecomment-490296365)
 */
module.exports = function () {
  const currentExports = __react_refresh_utils__.getModuleExports(module.id);
  __react_refresh_utils__.registerExportsForReactRefresh(currentExports, module.id);

  if (module.hot) {
    const isHotUpdate = !!module.hot.data;
    const prevExports = isHotUpdate ? module.hot.data.prevExports : null;

    if (__react_refresh_utils__.isReactRefreshBoundary(currentExports)) {
      module.hot.dispose(
        /**
         * A callback to performs a full refresh if React has unrecoverable errors,
         * and also caches the to-be-disposed module.
         * @param {*} data A hot module data object from Webpack HMR.
         * @returns {void}
         */
        function hotDisposeCallback(data) {
          // We have to mutate the data object to get data registered and cached
          data.prevExports = currentExports;
        }
      );
      module.hot.accept(
        /**
         * An error handler to allow self-recovering behaviours.
         * @param {Error} error An error occurred during evaluation of a module.
         * @returns {void}
         */
        function hotErrorHandler(error) {
          if (
            typeof __react_refresh_error_overlay__ !== 'undefined' &&
            __react_refresh_error_overlay__
          ) {
            __react_refresh_error_overlay__.handleRuntimeError(error);
          }

          if (typeof __react_refresh_test__ !== 'undefined' && __react_refresh_test__) {
            if (window.onHotAcceptError) {
              window.onHotAcceptError(error.message);
            }
          }

          __webpack_require__.c[module.id].hot.accept(hotErrorHandler);
        }
      );

      if (isHotUpdate) {
        if (
          __react_refresh_utils__.isReactRefreshBoundary(prevExports) &&
          __react_refresh_utils__.shouldInvalidateReactRefreshBoundary(prevExports, currentExports)
        ) {
          module.hot.invalidate();
        } else {
          __react_refresh_utils__.enqueueUpdate(
            /**
             * A function to dismiss the error overlay after performing React refresh.
             * @returns {void}
             */
            function updateCallback() {
              if (
                typeof __react_refresh_error_overlay__ !== 'undefined' &&
                __react_refresh_error_overlay__
              ) {
                __react_refresh_error_overlay__.clearRuntimeErrors();
              }
            }
          );
        }
      }
    } else {
      if (isHotUpdate && __react_refresh_utils__.isReactRefreshBoundary(prevExports)) {
        module.hot.invalidate();
      }
    }
  }
};
