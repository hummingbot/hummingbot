'use strict';

const success = (a) => [null, a];
const fail = (a) => [a];

const noArg = (f, a) => () => f(...a);

module.exports = (fn, ...args) => {
    check(fn);
    
    return Promise.resolve()
        .then(noArg(fn, args))
        .then(success)
        .catch(fail);
};

function check(fn) {
    if (typeof fn !== 'function')
        throw Error('fn should be a function!');
}

