'use strict';

module.exports = function tryCatch(fn) {
    var args = [].slice.call(arguments, 1);
    
    try {
        return [null, fn.apply(null, args)];
    } catch(e) {
        return [e];
    }
};

