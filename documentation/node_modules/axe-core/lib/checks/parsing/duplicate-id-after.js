var uniqueIds = [];
return results.filter(function(r) {
	if (uniqueIds.indexOf(r.data) === -1) {
		uniqueIds.push(r.data);
		return true;
	}
	return false;
});
