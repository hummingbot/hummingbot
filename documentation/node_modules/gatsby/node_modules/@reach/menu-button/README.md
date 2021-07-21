# @reach/menu-button

[![Stable release](https://img.shields.io/npm/v/@reach/menu-button.svg)](https://npm.im/@reach/menu-button) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/menu-button) | [Source](https://github.com/reach/reach-ui/tree/master/packages/menu-button) | [WAI-ARIA](https://www.w3.org/TR/wai-aria-practices-1.2/#menubutton)

An accessible dropdown menu for the common dropdown menu button design pattern.

```jsx
import {
  Menu,
  MenuList,
  MenuButton,
  MenuItem,
  MenuLink,
} from "@reach/menu-button";
import "@reach/menu-button/styles.css";

function Example() {
  return (
    <Menu>
      <MenuButton>
        Actions <span aria-hidden>▾</span>
      </MenuButton>
      <MenuList>
        <MenuItem onSelect={() => alert("Download")}>Download</MenuItem>
        <MenuItem onSelect={() => alert("Copy")}>Create a Copy</MenuItem>
        <MenuItem onSelect={() => alert("Mark as Draft")}>
          Mark as Draft
        </MenuItem>
        <MenuItem onSelect={() => alert("Delete")}>Delete</MenuItem>
        <MenuLink as="a" href="https://reacttraining.com/workshops/">
          Attend a Workshop
        </MenuLink>
      </MenuList>
    </Menu>
  );
}
```
