(function() {
    if (typeof Promise === 'undefined') {
        ES6Promise.polyfill();
    }
})();
