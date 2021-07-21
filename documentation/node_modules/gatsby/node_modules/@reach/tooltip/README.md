# @reach/tooltip

[![Stable release](https://img.shields.io/npm/v/@reach/tooltip.svg)](https://npm.im/@reach/tooltip) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/tooltip) | [Source](https://github.com/reach/reach-ui/tree/master/packages/tooltip) | [WAI-ARIA](https://www.w3.org/TR/wai-aria-practices-1.2/#tooltip)

When the user's mouse or focus rests on an element, a non-interactive popup is displayed near it.

A couple notes on using tooltips:

- Do not use tooltips for information vital to task completion. The elements they are attached to should usually make sense on their own, but a tooltip can help provide a little bit more information--especially for new users of your app.
- Keep the content minimal, they are not intended to hide critical content.
- If you want interactive content, you can use a [Dialog](/dialog).

_Touch Events_: Touch events are currently not supported. There's not a lot of research or examples of these types of tooltips on mobile. We have some ideas but need to validate them first before implementing. Please adjust your interfaces on mobile to account for this.

```jsx
import Tooltip, { useTooltip, TooltipPopup } from "@reach/tooltip";
import VisuallyHidden from "@reach/visually-hidden";
import "@reach/tooltip/styles.css";

function Example() {
  return (
    <Tooltip label="Save">
      <button>
        <VisuallyHidden>Save</VisuallyHidden>
        <span aria-hidden>💾</span>
      </button>
    </Tooltip>
  );
}
```
