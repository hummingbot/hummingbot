# @reach/portal

[![Stable release](https://img.shields.io/npm/v/@reach/portal.svg)](https://npm.im/@reach/portal) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/portal) | [Source](https://github.com/reach/reach-ui/tree/main/packages/portal)

Creates and appends a DOM node to the end of `document.body` and renders a React tree into it. Useful for rendering a natural React element hierarchy with a different DOM hierarchy to prevent parent styles from clipping or hiding content (for popovers, dropdowns, and modals).

```jsx
import Portal from "@reach/portal";

function Example() {
  return (
    <Portal>
      <div>Stuff goes here</div>
    </Portal>
  );
}
```
