var title = document.title;
return !!(title ? axe.commons.text.sanitize(title).trim() : '');
