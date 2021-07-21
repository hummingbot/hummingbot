# @reach/dialog

[![Stable release](https://img.shields.io/npm/v/@reach/dialog.svg)](https://npm.im/@reach/dialog) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/dialog) | [Source](https://github.com/reach/reach-ui/tree/master/packages/dialog) | [WAI-ARIA](https://www.w3.org/TR/wai-aria-practices-1.2/#dialog_modal)

An accessible dialog or modal window.

```jsx
import { Dialog } from "@reach/dialog";
import "@reach/dialog/styles.css";

function Example(props) {
  const [showDialog, setShowDialog] = React.useState(false);
  const open = () => setShowDialog(true);
  const close = () => setShowDialog(false);

  return (
    <div>
      <button onClick={open}>Open Dialog</button>
      <Dialog isOpen={showDialog} onDismiss={close}>
        <button className="close-button" onClick={close}>
          <VisuallyHidden>Close</VisuallyHidden>
          <span aria-hidden>×</span>
        </button>
        <p>Hello there. I am a dialog</p>
      </Dialog>
    </div>
  );
}
```
