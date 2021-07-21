/*
	MIT License http://www.opensource.org/licenses/mit-license.php
	Author Tobias Koppers @sokra
*/
var getNumberOfLines = require("./helpers").getNumberOfLines;
var getUnfinishedLine = require("./helpers").getUnfinishedLine;

function CodeNode(generatedCode) {
	this.generatedCode = generatedCode;
}
module.exports = CodeNode;

CodeNode.prototype.clone = function() {
	return new CodeNode(this.generatedCode);
}

CodeNode.prototype.getGeneratedCode = function() {
	return this.generatedCode;
};

CodeNode.prototype.getMappings = function(mappingsContext) {
	var lines = getNumberOfLines(this.generatedCode);
	var mapping = Array(lines+1).join(";");
	if(lines > 0) {
		mappingsContext.unfinishedGeneratedLine = getUnfinishedLine(this.generatedCode);
		if(mappingsContext.unfinishedGeneratedLine > 0) {
			return mapping + "A";
		} else {
			return mapping;
		}
	} else {
		var prevUnfinished = mappingsContext.unfinishedGeneratedLine;
		mappingsContext.unfinishedGeneratedLine += getUnfinishedLine(this.generatedCode);
		if(prevUnfinished === 0 && mappingsContext.unfinishedGeneratedLine > 0) {
			return "A";
		} else {
			return "";
		}
	}
};

CodeNode.prototype.addGeneratedCode = function(generatedCode) {
	this.generatedCode += generatedCode;
};

CodeNode.prototype.mapGeneratedCode = function(fn) {
	var generatedCode = fn(this.generatedCode);
	return new CodeNode(generatedCode);
};

CodeNode.prototype.getNormalizedNodes = function() {
	return [this];
};

CodeNode.prototype.merge = function merge(otherNode) {
	if(otherNode instanceof CodeNode) {
		this.generatedCode += otherNode.generatedCode;
		return this;
	}
	return false;
};
