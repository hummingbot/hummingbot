const { isXHTML } = axe.utils;

const langValue = (node.getAttribute(`lang`) || '').trim();
const xmlLangValue = (node.getAttribute(`xml:lang`) || '').trim();

if (!langValue && xmlLangValue && !isXHTML(document)) {
	this.data({
		messageKey: 'noXHTML'
	});
	return false;
}

if (!(langValue || xmlLangValue)) {
	this.data({
		messageKey: 'noLang'
	});
	return false;
}

return true;
