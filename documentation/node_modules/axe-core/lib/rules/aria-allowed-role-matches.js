return (
	axe.commons.aria.getRole(node, {
		noImplicit: true,
		dpub: true,
		fallback: true
	}) !== null
);
