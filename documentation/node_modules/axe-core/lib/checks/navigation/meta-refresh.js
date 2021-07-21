var content = node.getAttribute('content') || '',
	parsedParams = content.split(/[;,]/);

return content === '' || parsedParams[0] === '0';
