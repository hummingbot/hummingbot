var fs = require('fs');
var path = require('path');

module.exports = function() {
	fs.readFile(path.join(__dirname, 'help.md'), (err, result) => {
		var help;

		if (err) throw err;

		help = result
			.toString()
			.replace('<%= version %>', require('../package.json').version);

		console.log('\n' + help + '\n');
	});
};
