# @reach/popover

[![Stable release](https://img.shields.io/npm/v/@reach/popover.svg)](https://npm.im/@reach/popover) ![MIT license](https://badgen.now.sh/badge/license/MIT)

```jsx
import React, { useRef, useState } from "react";
import Popover, { positionDefault } from "@reach/popover";

function Example() {
  const ref = useRef(null);
  const [value, setValue] = useState("");
  return (
    <div>
      <label>
        <span>Type for a special message</span>
        <input
          type="text"
          ref={ref}
          onChange={event => setValue(event.target.value)}
        />
      </label>

      {value.length > 0 && (
        <Popover targetRef={ref} position={positionDefault}>
          <div>
            <p>Whoa! Look at me!</p>
          </div>
        </Popover>
      )}
    </div>
  );
}
```
