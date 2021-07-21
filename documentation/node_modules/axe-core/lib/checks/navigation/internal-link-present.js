const links = axe.utils.querySelectorAll(virtualNode, 'a[href]');
return links.some(vLink => {
	return /^#[^/!]/.test(vLink.actualNode.getAttribute('href'));
});
