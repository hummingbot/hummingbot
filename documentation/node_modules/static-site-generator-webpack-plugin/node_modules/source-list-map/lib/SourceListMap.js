/*
	MIT License http://www.opensource.org/licenses/mit-license.php
	Author Tobias Koppers @sokra
*/
var CodeNode = require("./CodeNode");
var SourceNode = require("./SourceNode");
var MappingsContext = require("./MappingsContext");
var getNumberOfLines = require("./helpers").getNumberOfLines;

function SourceListMap(generatedCode, source, originalSource) {
	if(Array.isArray(generatedCode)) {
		this.children = generatedCode;
	} else {
		this.children = [];
		if(generatedCode || source)
			this.add(generatedCode, source, originalSource);
	}
}
module.exports = SourceListMap;

SourceListMap.prototype.add = function(generatedCode, source, originalSource) {
	if(typeof generatedCode === "string") {
		if(source) {
			this.children.push(new SourceNode(generatedCode, source, originalSource));
		} else if(this.children.length > 0 && this.children[this.children.length - 1] instanceof CodeNode) {
			this.children[this.children.length - 1].addGeneratedCode(generatedCode);
		} else {
			this.children.push(new CodeNode(generatedCode));
		}
	} else if(generatedCode.getMappings && generatedCode.getGeneratedCode) {
		this.children.push(generatedCode);
	} else if(generatedCode.children) {
		generatedCode.children.forEach(function(sln) {
			this.children.push(sln);
		}, this);
	} else {
		throw new Error("Invalid arguments to SourceListMap.prototype.add: Expected string, Node or SourceListMap");
	}
};

SourceListMap.prototype.preprend = function(generatedCode, source, originalSource) {
	if(typeof generatedCode === "string") {
		if(source) {
			this.children.unshift(new SourceNode(generatedCode, source, originalSource));
		} else if(this.children.length > 0 && this.children[this.children.length - 1].preprendGeneratedCode) {
			this.children[this.children.length - 1].preprendGeneratedCode(generatedCode);
		} else {
			this.children.unshift(new CodeNode(generatedCode));
		}
	} else if(generatedCode.getMappings && generatedCode.getGeneratedCode) {
		this.children.unshift(generatedCode);
	} else if(generatedCode.children) {
		generatedCode.children.slice().reverse().forEach(function(sln) {
			this.children.unshift(sln);
		}, this);
	} else {
		throw new Error("Invalid arguments to SourceListMap.prototype.prerend: Expected string, Node or SourceListMap");
	}
};

SourceListMap.prototype.mapGeneratedCode = function(fn) {
	var normalizedNodes = [];
	this.children.forEach(function(sln) {
		sln.getNormalizedNodes().forEach(function(newNode) {
			normalizedNodes.push(newNode);
		});
	});
	var optimizedNodes = [];
	normalizedNodes.forEach(function(sln) {
		sln = sln.mapGeneratedCode(fn);
		if(optimizedNodes.length === 0) {
			optimizedNodes.push(sln);
		} else {
			var last = optimizedNodes[optimizedNodes.length - 1];
			var mergedNode = last.merge(sln);
			if(mergedNode) {
				optimizedNodes[optimizedNodes.length - 1] = mergedNode;
			} else {
				optimizedNodes.push(sln);
			}
		}
	});
	return new SourceListMap(optimizedNodes);
};

SourceListMap.prototype.toString = function() {
	return this.children.map(function(sln) {
		return sln.getGeneratedCode();
	}).join("");
};

SourceListMap.prototype.toStringWithSourceMap = function(options) {
	var mappingsContext = new MappingsContext();
	var source = this.children.map(function(sln) {
		return sln.getGeneratedCode();
	}).join("");
	var mappings = this.children.map(function(sln) {
		return sln.getMappings(mappingsContext);
	}).join("");
	return {
		source: source,
		map: {
			version: 3,
			file: options && options.file,
			sources: mappingsContext.sources,
			sourcesContent: mappingsContext.hasSourceContent ? mappingsContext.sourcesContent : undefined,
			mappings: mappings
		}
	};
}
