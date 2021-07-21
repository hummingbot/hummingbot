var seen = {};

// Filter out nodes that have the same type and name.
// If you have two `<input type="radio" name="foo" />` elements
// only the first one can pass / fail the rule.
return results.filter(function(result) {
	var data = result.data;
	if (data) {
		seen[data.type] = seen[data.type] || {};
		if (!seen[data.type][data.name]) {
			seen[data.type][data.name] = true;
			return true;
		}
	}
	return false;
});
