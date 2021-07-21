/*
	MIT License http://www.opensource.org/licenses/mit-license.php
	Author Tobias Koppers @sokra
*/
var Source = require("./Source");
var SourceNode = require("source-map").SourceNode;

var REPLACE_REGEX = /\n(?=.|\s)/g

function PrefixSource(prefix, source) {
	Source.call(this);
	this._source = source;
	this._prefix = prefix;
}
module.exports = PrefixSource;

PrefixSource.prototype = Object.create(Source.prototype);
PrefixSource.prototype.constructor = PrefixSource;

PrefixSource.prototype.source = function() {
	var node = typeof this._source === "string" ? this._source : this._source.source();
	var prefix = this._prefix;
	return prefix + node.replace(REPLACE_REGEX, "\n" + prefix);
};

require("./SourceAndMapMixin")(PrefixSource.prototype);

PrefixSource.prototype.node = function(options) {
	var node = this._source.node(options);
	var append = [this._prefix];
	return new SourceNode(null, null, null, [
		cloneAndPrefix(node, this._prefix, append)
	]);
};

PrefixSource.prototype.listMap = function(options) {
	var prefix = this._prefix;
	var map = this._source.listMap(options);
	return map.mapGeneratedCode(function(code) {
		return prefix + code.replace(REPLACE_REGEX, "\n" + prefix);
	});
};

PrefixSource.prototype.updateHash = function(hash) {
	if(typeof this._source === "string")
		hash.update(this._source);
	else
		this._source.updateHash(hash);
	if(typeof this._prefix === "string")
		hash.update(this._prefix);
	else
		this._prefix.updateHash(hash);
};

function cloneAndPrefix(node, prefix, append) {
	if(typeof node === "string") {
		var result = node.replace(REPLACE_REGEX, "\n" + prefix);
		if(append.length > 0) result = append.pop() + result;
		if(/\n$/.test(node)) append.push(prefix);
		return result;
	} else {
		var newNode = new SourceNode(
			node.line,
			node.column,
			node.source,
			node.children.map(function(node) {
				return cloneAndPrefix(node, prefix, append);
			}),
			node.name
		);
		newNode.sourceContents = node.sourceContents;
		return newNode;
	}
};
