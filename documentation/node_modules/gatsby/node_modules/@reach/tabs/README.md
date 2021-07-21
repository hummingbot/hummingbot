# @reach/tabs

[![Stable release](https://img.shields.io/npm/v/@reach/tabs.svg)](https://npm.im/@reach/tabs) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/tabs) | [Source](https://github.com/reach/reach-ui/tree/master/packages/tabs) | [WAI-ARIA](https://www.w3.org/TR/wai-aria-practices-1.2/#tabpanel)

An accessible tabs component.

The `Tab` and `TabPanel` elements are associated by their order in the tree. None of the components are empty wrappers, each is associated with a real DOM element in the document, giving you maximum control over styling and composition.

You can render any other elements you want inside of `Tabs`, but `TabList` should only render `Tab` elements, and `TabPanels` should only render `TabPanel` elements.

```jsx
import { Tabs, TabList, Tab, TabPanels, TabPanel } from "@reach/tabs";
import "@reach/tabs/styles.css";

function Example() {
  return (
    <Tabs>
      <TabList>
        <Tab>One</Tab>
        <Tab>Two</Tab>
        <Tab>Three</Tab>
      </TabList>

      <TabPanels>
        <TabPanel>
          <p>one!</p>
        </TabPanel>
        <TabPanel>
          <p>two!</p>
        </TabPanel>
        <TabPanel>
          <p>three!</p>
        </TabPanel>
      </TabPanels>
    </Tabs>
  );
}
```
