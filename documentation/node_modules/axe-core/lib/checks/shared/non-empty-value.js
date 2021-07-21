var label = node.getAttribute('value');
return !!(label ? axe.commons.text.sanitize(label).trim() : '');
