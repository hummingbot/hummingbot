const tracks = axe.utils.querySelectorAll(virtualNode, 'track');
const hasDescriptions = tracks.some(
	({ actualNode }) =>
		(actualNode.getAttribute('kind') || '').toLowerCase() === 'descriptions'
);

// Undefined if there are no tracks - media may have another description method
return hasDescriptions ? false : undefined;
