const alt = virtualNode.attr('alt');
const isOnlySpace = /^\s+$/;
return typeof alt === 'string' && isOnlySpace.test(alt);
