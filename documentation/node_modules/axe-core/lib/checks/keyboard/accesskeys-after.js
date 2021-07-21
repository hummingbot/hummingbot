var seen = {};
return results
	.filter(function(r) {
		if (!r.data) {
			return false;
		}
		var key = r.data.toUpperCase();
		if (!seen[key]) {
			seen[key] = r;
			r.relatedNodes = [];
			return true;
		}
		seen[key].relatedNodes.push(r.relatedNodes[0]);
		return false;
	})
	.map(function(r) {
		r.result = !!r.relatedNodes.length;
		return r;
	});
