var filesystem = require('../../');
var test = require('tape');
var levelup = require('levelup');
var memdown = require('memdown');

var reset = function() {
	return filesystem(levelup('memdb', {db:memdown}));
};

module.exports = function(name, fn) {
	test(name, function(t) {
		fn(reset(), t);
	});
};