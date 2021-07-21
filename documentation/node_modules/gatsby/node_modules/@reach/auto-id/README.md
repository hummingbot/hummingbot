# @reach/auto-id

[![Stable release](https://img.shields.io/npm/v/@reach/auto-id.svg)](https://npm.im/@reach/auto-id) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/auto-id) | [Source](https://github.com/reach/reach-ui/tree/main/packages/auto-id)

Autogenerate IDs to facilitate WAI-ARIA and server rendering.

A string can be supplied as an argument to be `useId` in lieu of the auto-generated ID. This is handy for accepting user-provided prop IDs that need to be deterministic.

```jsx
import { useId } from "@reach/auto-id";

function FormField(props) {
  const id = useId(props.id);
  return (
    <Fragment>
      <label htmlFor={id}>{props.label}</label>
      <input type={props.type} name={props.name} id={id} />
    </Fragment>
  );
}
```
