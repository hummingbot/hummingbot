# @reach/visually-hidden

[![Stable release](https://img.shields.io/npm/v/@reach/visually-hidden.svg)](https://npm.im/@reach/visually-hidden) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/visually-hidden) | [Source](https://github.com/reach/reach-ui/tree/main/packages/visually-hidden) | [Origin](https://snook.ca/archives/html_and_css/hiding-content-for-accessibility) | [Further reading](https://a11yproject.com/posts/how-to-hide-content/)

Provides text for screen readers that is visually hidden. It is the logical opposite of the `aria-hidden` attribute.

In the following example, screen readers will announce "Save" and will ignore the icon; the browser displays the icon and ignores the text.

```jsx
import VisuallyHidden from "@reach/visually-hidden";

function Example() {
  return (
    <button>
      <VisuallyHidden>Save</VisuallyHidden>
      <span aria-hidden>💾</span>
    </button>
  );
}
```
