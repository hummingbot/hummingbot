var title = axe.commons.text
	.sanitize(node.title)
	.trim()
	.toLowerCase();
this.data(title);
return true;
