const safeThis = require('./utils/safeThis');

if (process.env.NODE_ENV !== 'production' && typeof safeThis !== 'undefined') {
  // Only inject the runtime if it hasn't been injected
  if (!safeThis.__reactRefreshInjected) {
    const RefreshRuntime = require('react-refresh/runtime');
    // Inject refresh runtime into global scope
    RefreshRuntime.injectIntoGlobalHook(safeThis);

    // Mark the runtime as injected to prevent double-injection
    safeThis.__reactRefreshInjected = true;
  }
}
