(function(axe) {
	var parser = new axe.imports.CssSelectorParser();
	parser.registerSelectorPseudos('not');
	parser.registerNestingOperators('>');
	parser.registerAttrEqualityMods('^', '$', '*');
	axe.utils.cssParser = parser;
})(axe);
