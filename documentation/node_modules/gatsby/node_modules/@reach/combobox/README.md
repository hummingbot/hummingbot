# @reach/combobox

[![Stable release](https://img.shields.io/npm/v/@reach/combobox.svg)](https://npm.im/@reach/combobox) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/combobox) | [Source](https://github.com/reach/reach-ui/tree/master/packages/combobox) | [WAI-ARIA](https://www.w3.org/TR/wai-aria-practices-1.2/#combobox)

Accessible combobox (autocomplete or autosuggest) component for React.

A combobox is the combination of an `<input type="text" />` and a list. The list is designed to help the user arrive at a value, but the value does not necessarily have to come from that list. Don't think of it like a `<select />`, but more of an `<input type="text" />` with some suggestions. You can, however, validate that the value comes from the list, that's up to your app.

```js
import {
  Combobox,
  ComboboxInput,
  ComboboxPopover,
  ComboboxList,
  ComboboxOption,
  ComboboxOptionText,
} from "@reach/combobox";
import "@reach/combobox/styles.css";

function Example() {
  return (
    <div>
      <Combobox>
        <ComboboxInput aria-labelledby="demo" />
        <ComboboxPopover>
          <ComboboxList aria-labelledby="demo">
            <ComboboxOption value="Apple" />
            <ComboboxOption value="Banana" />
            <ComboboxOption value="Orange" />
            <ComboboxOption value="Pineapple" />
            <ComboboxOption value="Kiwi" />
          </ComboboxList>
        </ComboboxPopover>
      </Combobox>
    </div>
  );
}
```
