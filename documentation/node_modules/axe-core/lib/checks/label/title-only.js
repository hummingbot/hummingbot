var labelText = axe.commons.text.labelVirtual(virtualNode);
return (
	!labelText &&
	!!(node.getAttribute('title') || node.getAttribute('aria-describedby'))
);
