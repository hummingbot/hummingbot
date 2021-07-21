/*eslint no-use-before-define:0 */
var axe = axe || {};
axe.plugins = {};

function Plugin(spec) {
	'use strict';
	this._run = spec.run;
	this._collect = spec.collect;
	this._registry = {};
	spec.commands.forEach(function(command) {
		axe._audit.registerCommand(command);
	});
}

Plugin.prototype.run = function() {
	'use strict';
	return this._run.apply(this, arguments);
};

Plugin.prototype.collect = function() {
	'use strict';
	return this._collect.apply(this, arguments);
};

Plugin.prototype.cleanup = function(done) {
	'use strict';
	var q = axe.utils.queue();
	var that = this;
	Object.keys(this._registry).forEach(function(key) {
		q.defer(function(done) {
			that._registry[key].cleanup(done);
		});
	});
	q.then(function() {
		done();
	});
};

Plugin.prototype.add = function(impl) {
	'use strict';
	this._registry[impl.id] = impl;
};

axe.registerPlugin = function(plugin) {
	'use strict';
	axe.plugins[plugin.id] = new Plugin(plugin);
};
