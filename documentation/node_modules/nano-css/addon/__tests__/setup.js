'use strict';

process.env.NODE_ENV = 'production';

if (typeof window === 'object') {
    global.requestAnimationFrame = window.requestAnimationFrame = function (callback) { return setTimeout(callback, 17); };
}
