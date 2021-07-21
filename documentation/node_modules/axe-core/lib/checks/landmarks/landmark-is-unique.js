var role = axe.commons.aria.getRole(node);
var accessibleText = axe.commons.text.accessibleTextVirtual(virtualNode);
accessibleText = accessibleText ? accessibleText.toLowerCase() : null;
this.data({ role: role, accessibleText: accessibleText });
this.relatedNodes([node]);

return true;
