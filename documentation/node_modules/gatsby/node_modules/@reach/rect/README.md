# @reach/rect

[![Stable release](https://img.shields.io/npm/v/@reach/rect.svg)](https://npm.im/@reach/rect) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/rect) | [Source](https://github.com/reach/reach-ui/tree/main/packages/rect)

Measures DOM elements (aka. bounding client rect). See also [Element.getBoundingClientRect()](https://developer.mozilla.org/en-US/docs/Web/API/Element/getBoundingClientRect)

```jsx
import Rect, { useRect } from "@reach/rect";

function Example() {
  const ref = useRef();
  const rect = useRect(ref);

  return (
    <div>
      <pre>{JSON.stringify(rect, null, 2)}</pre>
      <div
        ref={ref}
        contentEditable
        dangerouslySetInnerHTML={{
          __html: "Edit this to change the size!",
        }}
      />
    </div>
  );
}
```
