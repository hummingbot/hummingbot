var title = node.getAttribute('title');
return !!(title ? axe.commons.text.sanitize(title).trim() : '');
