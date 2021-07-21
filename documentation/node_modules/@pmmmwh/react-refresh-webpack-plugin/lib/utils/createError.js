/**
 * Creates an error with the plugin's prefix.
 * @param {string} message The error's message.
 * @returns {Error} The created error object.
 */
function createError(message) {
  return new Error(`[React Refresh] ${message}`);
}

module.exports = createError;
