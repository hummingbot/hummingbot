options = options || {};
var value = node.getAttribute('scope').toLowerCase();
var validVals = ['row', 'col', 'rowgroup', 'colgroup'] || options.values;

return validVals.indexOf(value) !== -1;
