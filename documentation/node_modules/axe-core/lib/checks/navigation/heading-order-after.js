if (results.length < 2) {
	return results;
}

var prevLevel = results[0].data;

for (var i = 1; i < results.length; i++) {
	if (results[i].result && results[i].data > prevLevel + 1) {
		results[i].result = false;
	}
	prevLevel = results[i].data;
}

return results;
