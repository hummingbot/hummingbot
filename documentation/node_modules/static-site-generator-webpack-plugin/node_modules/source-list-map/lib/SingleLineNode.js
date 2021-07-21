/*
	MIT License http://www.opensource.org/licenses/mit-license.php
	Author Tobias Koppers @sokra
*/
module.exports = SingleLineNode; // circular dependency

var base64VLQ = require("./base64-vlq");
var getNumberOfLines = require("./helpers").getNumberOfLines;
var getUnfinishedLine = require("./helpers").getUnfinishedLine;
var SourceNode = require("./SourceNode");

function SingleLineNode(generatedCode, source, originalSource, line) {
	this.generatedCode = generatedCode;
	this.originalSource = originalSource;
	this.source = source;
	this.line = line || 1;
	this._numberOfLines = getNumberOfLines(this.generatedCode);
	this._endsWithNewLine = generatedCode[generatedCode.length - 1] === "\n";
}

SingleLineNode.prototype.clone = function() {
	return new SingleLineNode(this.generatedCode, this.source, this.originalSource, this.line);
}

var LINE_MAPPING = ";AAAA";

SingleLineNode.prototype.getGeneratedCode = function() {
	return this.generatedCode;
};

SingleLineNode.prototype.getMappings = function(mappingsContext) {
	if(!this.generatedCode)
		return "";
	var lines = this._numberOfLines;
	var sourceIdx = mappingsContext.ensureSource(this.source, this.originalSource);
	var mappings = "A"; // generated column 0
	if(mappingsContext.unfinishedGeneratedLine)
		mappings = "," + base64VLQ.encode(mappingsContext.unfinishedGeneratedLine);
	mappings += base64VLQ.encode(sourceIdx - mappingsContext.currentSource); // source index
	mappings += base64VLQ.encode(this.line - mappingsContext.currentOriginalLine); // original line index
	mappings += "A"; // original column 0
	mappingsContext.currentSource = sourceIdx;
	mappingsContext.currentOriginalLine = this.line;
	var unfinishedGeneratedLine = mappingsContext.unfinishedGeneratedLine = getUnfinishedLine(this.generatedCode)
	mappings += Array(lines).join(LINE_MAPPING);
	if(unfinishedGeneratedLine === 0) {
		mappings += ";";
	} else {
		if(lines !== 0)
			mappings += LINE_MAPPING;
	}
	return mappings;
};

SingleLineNode.prototype.getNormalizedNodes = function() {
	return [this];
};

SingleLineNode.prototype.mapGeneratedCode = function(fn) {
	var generatedCode = fn(this.generatedCode);
	return new SingleLineNode(generatedCode, this.source, this.originalSource, this.line);
};

SingleLineNode.prototype.merge = function merge(otherNode) {
	if(otherNode instanceof SingleLineNode) {
		return this.mergeSingleLineNode(otherNode);
	}
	return false;
};

SingleLineNode.prototype.mergeSingleLineNode = function mergeSingleLineNode(otherNode) {
	if(this.source === otherNode.source &&
		this.originalSource === otherNode.originalSource) {
		if(this.line === otherNode.line) {
			this.generatedCode += otherNode.generatedCode;
			this._numberOfLines += otherNode._numberOfLines;
			this._endsWithNewLine = otherNode._endsWithNewLine;
			return this;
		} else if(this.line + 1 === otherNode.line && 
			this._endsWithNewLine &&
			this._numberOfLines === 1 && 
			otherNode._numberOfLines <= 1) {
			return new SourceNode(this.generatedCode + otherNode.generatedCode, this.source, this.originalSource, this.line);
		}
	}
	return false;
};
