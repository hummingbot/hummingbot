'use strict';
const path = require('path');

module.exports = (childPath, parentPath) => {
	childPath = path.resolve(childPath);
	parentPath = path.resolve(parentPath);

	if (process.platform === 'win32') {
		childPath = childPath.toLowerCase();
		parentPath = parentPath.toLowerCase();
	}

	if (childPath === parentPath) {
		return false;
	}

	childPath += path.sep;
	parentPath += path.sep;

	return childPath.startsWith(parentPath);
};
