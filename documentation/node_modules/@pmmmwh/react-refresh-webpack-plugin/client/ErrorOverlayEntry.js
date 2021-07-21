/* global __react_refresh_error_overlay__, __react_refresh_init_socket__, __resourceQuery */

const errorEventHandlers = require('./utils/errorEventHandlers');
const formatWebpackErrors = require('./utils/formatWebpackErrors');

// Setup error states
let isHotReload = false;
let hasRuntimeErrors = false;

/**
 * Try dismissing the compile error overlay.
 * This will also reset runtime error records (if any),
 * because we have new source to evaluate.
 * @returns {void}
 */
function tryDismissErrorOverlay() {
  __react_refresh_error_overlay__.clearCompileError();
  __react_refresh_error_overlay__.clearRuntimeErrors(!hasRuntimeErrors);
  hasRuntimeErrors = false;
}

/**
 * A function called after a compile success signal is received from Webpack.
 * @returns {void}
 */
function handleCompileSuccess() {
  isHotReload = true;

  if (isHotReload) {
    tryDismissErrorOverlay();
  }
}

/**
 * A function called after a compile errored signal is received from Webpack.
 * @param {string} errors
 * @returns {void}
 */
function handleCompileErrors(errors) {
  isHotReload = true;

  const formattedErrors = formatWebpackErrors(errors);

  // Only show the first error
  __react_refresh_error_overlay__.showCompileError(formattedErrors[0]);
}

/**
 * Handles compilation messages from Webpack.
 * Integrates with a compile error overlay.
 * @param {*} message A Webpack HMR message sent via WebSockets.
 * @returns {void}
 */
function compileMessageHandler(message) {
  switch (message.type) {
    case 'ok':
    case 'still-ok':
    case 'warnings': {
      // TODO: Implement handling for warnings
      handleCompileSuccess();
      break;
    }
    case 'errors': {
      handleCompileErrors(message.data);
      break;
    }
    default: {
      // Do nothing.
    }
  }
}

// Only register if we're in non-production mode and if window is defined
if (process.env.NODE_ENV !== 'production' && typeof window !== 'undefined') {
  // Registers handlers for compile errors
  __react_refresh_init_socket__(compileMessageHandler, __resourceQuery);
  // Registers handlers for runtime errors
  errorEventHandlers.error(function handleError(error) {
    hasRuntimeErrors = true;
    __react_refresh_error_overlay__.handleRuntimeError(error);
  });
  errorEventHandlers.unhandledRejection(function handleUnhandledPromiseRejection(error) {
    hasRuntimeErrors = true;
    __react_refresh_error_overlay__.handleRuntimeError(error);
  });
}
