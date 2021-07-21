var seen = {};

return results.filter(function(result) {
	// passes can pass through
	if (result.result) {
		return true;
	}
	var data = result.data;
	if (data) {
		seen[data.type] = seen[data.type] || {};
		if (!seen[data.type][data.name]) {
			seen[data.type][data.name] = [data];
			return true;
		}
		var hasBeenSeen = seen[data.type][data.name].some(function(candidate) {
			return candidate.failureCode === data.failureCode;
		});
		if (!hasBeenSeen) {
			seen[data.type][data.name].push(data);
		}

		return !hasBeenSeen;
	}
	return false;
});
