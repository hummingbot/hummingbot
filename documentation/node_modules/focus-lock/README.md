# focus-lock
It is a trap! We got your focus and will not let him out!

[![NPM](https://nodei.co/npm/focus-lock.png?downloads=true&stars=true)](https://nodei.co/npm/react-focus-lock/)

# Consumers

This is a base package for:
  - [react-focus-lock](https://github.com/theKashey/react-focus-lock)
  [![downloads](https://badgen.net/npm/dm/react-focus-lock)](https://www.npmtrends.com/react-focus-lock)
  - [vue-focus-lock](https://github.com/theKashey/vue-focus-lock)
  [![downloads](https://badgen.net/npm/dm/vue-focus-lock)](https://www.npmtrends.com/vue-focus-lock)
  - [dom-focus-lock](https://github.com/theKashey/dom-focus-lock)
  [![downloads](https://badgen.net/npm/dm/dom-focus-lock)](https://www.npmtrends.com/dom-focus-lock)

Provides a low level API, to be used by final realization. Usually everything
can be solved in 3 lines
```js
import moveFocusInside, { focusInside } from 'focus-lock';

if (topNode && !focusInside(topNode)) {
  moveFocusInside(topNode, lastActiveFocus);
}
```

# WHY?
From [MDN Article about accessible dialogs](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/ARIA_Techniques/Using_the_dialog_role):
 - The dialog must be properly labeled
 - Keyboard __focus must be managed__ correctly
 
This one is about managing the focus.

I'v got a good [article about focus management, dialogs and  WAI-ARIA](https://medium.com/@antonkorzunov/its-a-focus-trap-699a04d66fb5).    

# Focus fighting
It is possible, that more that one "focus management system" is present on the site.
For example you are using FocusLock for your content, and also using some
Modal dialog, with FocusTrap inside.

Both system will try to do their best, and move focus into their managed areas.
Stack overflow. Both are dead.

Focus Lock(React-Focus-Lock, Vue-Focus-Lock and so on) implements anti-fighting
protection - once the battle is detected focus-lock will surrender(as long there is no way to win this fight).

You may also land a peace by special data attribute - `data-no-focus-lock`(constants.FOCUS_ALLOW). It will
remove focus management from all nested elements, letting you open modals, forms, or 
use any third party component safely. Focus lock will just do nothing, while focus is on the marked elements. 

# API

`default(topNode, lastNode)` (aka setFocus), moves focus inside topNode, keeping in mind that last focus inside was - lastNode
 
# Licence
 MIT
 
 
