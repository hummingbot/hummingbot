var titles = {};
results.forEach(function(r) {
	titles[r.data] = titles[r.data] !== undefined ? ++titles[r.data] : 0;
});
results.forEach(function(r) {
	r.result = !!titles[r.data];
});

return results;
