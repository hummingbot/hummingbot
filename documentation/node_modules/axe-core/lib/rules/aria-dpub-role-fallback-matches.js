var role = node.getAttribute('role');
return [
	'doc-backlink',
	'doc-biblioentry',
	'doc-biblioref',
	'doc-cover',
	'doc-endnote',
	'doc-glossref',
	'doc-noteref'
].includes(role);
