# @reach/descendants

[![Stable release](https://img.shields.io/npm/v/@reach/descendants.svg)](https://npm.im/@reach/descendants) ![MIT license](https://badgen.now.sh/badge/license/MIT)

A descendant index solution for better accessibility support in compound components.

**Important:** This package is primarily intended for internal use by the Reach UI library. You should probably not use it directly in your production projects, as the APIs can still change with minor version bumps (at least until we're comfortable releasing a 1.0). You have been warned!

## The Problem

In React you can wrap up any elements into a component and then render the new component instead. It's beautiful.

```jsx
// old
<h1>Time zones</h1>
<select>
  <option>Eastern</option>
  <option>Central</option>
  <option>Mountain</option>
  <option>Pacific</option>
  <option>UTC-10</option>
  <option>UTC-09</option>
  <option>UTC-09:30</option>
  {/* etc. */}
</select>

// new
<h1>Time zones</h1>
<select>
  <LocaleTimeZoneOptions/>
  <UTCTimeZoneOptions/>
</select>

function LocaleTimeZoneOptions() {
  return (
    <>
      <option>Eastern</option>
      <option>Central</option>
      <option>Mountain</option>
      <option>Pacific</option>
    </>
  )
}
```

Everything will continue to work!

But when we want to create our own abstractions like this, we can't always abstract and compose the same way.

The Menu here will set an `aria-activedescendant={activeElementId}` so that assistive tech can announce correctly. The menu also needs a ref to the children so it can set them as the active descendant (or actually focus the node) from keyboard events like `ArrowUp` and `ArrowDown`.

Additionally, `MenuItem` needs to know if it is the active descendant so it can style itself differently.

```jsx
<Menu>
  <MenuItem onSelect={download}>Download</MenuItem>
  <MenuItem onSelect={save}>Save</MenuItem>
  <MenuItem onSelect={preview}>Preview</MenuItem>
</Menu>
```

There are a few ways to deal with this.

## Option 1: Bail out of Elements

The solution most people turn to is to bail out of the element API and turn to arrays. This lets a single owner control the state and rendering, makes it way easier to know the index and set the active descendant.

```jsx
<Menu
  items={[
    { label: "Download", onSelect: download },
    { label: "Save", onSelect: save },
    { label: "Preview", onSelect: preview },
  ]}
/>;

function Menu({ items }) {
  const [activeIndex, setActiveIndex] = useState();
  return (
    <div data-menu aria-activedescendant={activeIndex}>
      {items.map((item, index) => (
        <MenuItem
          // easy to tell the index
          index={index}
          activeIndex={activeIndex}
          onSelect={item.onSelect}
        >
          {item.label}
        </MenuItem>
      ))}
    </div>
  );
}

function MenuItem({ index, activeIndex, onSelect, children }) {
  // and now we can style
  const isActive = index === activeIndex;
  return (
    <div
      // and add an ID
      id={index}
      data-highlighted={isActive ? "" : undefined}
    >
      {children}
    </div>
  );
}
```

This is where most people live. You see these APIs everywhere because it's way easier when you own all the state and all the elements in one place. But you lose composition.

What happens when we want to add a className to all, one, or just a few of the elements? You end up with weird APIs like:

```jsx
<Menu
  options={[
    { label: "Download", onSelect: download },
    { label: "Save", onSelect: save },
    { label: "Preview", onSelect: preview },
  ]}
  // stuff like this
  optionClassNames="cool"
  // or shoot, we need more than classNames
  optionsProps={{
    className: "cool",
    onMouseEnter: handler,
  }}
  // dangit we need to do it differently depending on the option
  getOptionProps={(option, index) => {
    return index === 2 ? "bg-blue" : "bg-white";
  }}
  // ah forget it, here you do it, enjoy the branching!
  renderOption={(option, index) => (
    <MenuItem
      className={index === 2 ? "bg-blue" : "bg-white"}
      aria-label={index === 2 ? "Preview Invoice" : undefined}
    >
      {index === 0 ? (
        <DownloadIcon />
      ) : index === 1 ? (
        <SaveIcon />
      ) : index === 2 ? (
        <PreviewIcon />
      ) : null}
      {option.label}
    </MenuItem>
  )}
/>
```

Because the rendering is in the same owner as the state, we have to poke holes in the component to change anything about how it renders.

All that, just so the stinking `MenuOption` knows its index in the parent's element tree.

Had we stuck to elements, we could have done this:

```jsx
<Menu>
  <MenuItem className="bg-white" onSelect={download}>
    <DownloadIcon /> Download
  </MenuItem>
  <MenuItem className="bg-white" onSelect={save}>
    <SaveIcon /> Save
  </MenuItem>
  <MenuItem
    className="bg-white"
    onSelect={preview}
    aria-label="Preview Invoice"
  >
    <PreviewIcon /> Preview
  </MenuItem>
</Menu>
```

But how will the `MenuItem` components know their index?

## Option 2: Type Checking and `cloneElement`

We can use `React.cloneElement` to keep (most of) the normal React composition. No more `items` prop. Instead we map the children, clone them, and pass them the state that we know in Menu.

```jsx
function Menu({ children }) {
  const [activeIndex, setActiveIndex] = useState();
  return (
    <div data-menu aria-activedescendant={activeIndex}>
      {React.Children.map(children, (child, index) =>
        React.cloneElement(child, { index, activeIndex })
      )}
    </div>
  );
}

function MenuItem({ index, activeIndex, onSelect, children }) {
  // index came from the clone
  const isActive = index === activeIndex;
  return (
    <div id={index} data-highlighted={isActive ? "" : undefined}>
      {children}
    </div>
  );
}
```

We've now seperated the state from the elements so that apps can compose however they please. If you want to put a `className` on one item and not another, you can, and we don't have to poke holes into our `Menu` component just to meet every use case that pops up.

Almost.

What if we need to put a div around one of the items?

```jsx
<Menu>
  <div>
    <MenuItem />
  </div>
  <MenuItem />
</Menu>
```

This is totally broken now because we cloned the `div`, not the `MenuItem`. You _could_ recurse down the tree and type check until you find a `MenuItem`, but…come on.

A recursive type check could help a little, but it still limits composition, what if you wanted to do this?

```jsx
function BlueItem(props) {
  return <MenuItem {...props} className="bg-blue" />;
}

<Menu>
  <MenuItem />
  <BlueItem />
</Menu>;
```

The type checking will fail 😭.

So now we need a way to define arbitrary components as a `MenuItem`. One workaround is a static property of the component to check instead of just `type`. The type checking changes from this `element.type === MenuItem` to this: `element.type.is === MenuItem`, and of course make sure apps assign `BlueItem.is = MenuItem`.

## Our solution (for now): Descendants context registration

The `descendants` package provides these key tools:

- `createDescendantContext`: Creates a special context object to deal with registering descendants in a tree (accepts a name string for better debugging)
- `useDescendants`: A hook to create a state object containing a descendants array and setter function.
- `DescendantProvider`: A provider that accepts the descendants array, the state setter, and the component's context object for use at the top of the component tree
- `useDescendant`: A hook called in the body of a nested descendant component that registers its DOM node and returns its index relative to other descendants in the tree

```jsx
import {
  createDescendantContext,
  DescendantProvider,
  useDescendant,
  useDescendants,
} from "@reach/descendants";

let DescendantContext = createDescendantContext("DescendantContext");
let MenuContext = createContext();

function Menu({ id, children }) {
  // We could be less explicit here and set this up in the DescendantProvider,
  // but you may want to do something with `descendants` in your top-level
  // component and we don't want to force creating an arbitrary child
  // component just so we can consume the context.
  let [descendants, setDescendants] = useDescendantsInit();
  let [activeIndex, setActiveIndex] = useState(-1);
  return (
    <DescendantProvider
      context={DescendantContext}
      items={descendants}
      set={setDescendants}
    >
      <MenuContext.Provider
        value={{ buttonId: `button-${useId(id)}`, activeIndex, setActiveIndex }}
      >
        {children}
      </MenuContext.Provider>
    </DescendantProvider>
  );
}

function MenuList(props) {
  let { buttonId, activeIndex } = useContext(MenuContext);
  return (
    <Popover>
      <div
        role="menu"
        aria-labelledby={buttonId}
        aria-activedescendant={activeIndex}
        tabIndex={-1}
      >
        {children}
      </div>
    </Popover>
  );
}

function MenuItem({ index: explicitIndex, ...props }) {
  let { activeIndex, setActiveIndex } = useContext(MenuContext);
  let ref = useRef(null);
  let index = useDescendant(
    {
      // Assign the DOM node using a ref
      element: ref.current,
      // You can pass arbitrary data into a descendant object which can come
      // in handy for features like typeahead!
      key: props.label,
    },
    // Tell the useDescendant hook to use a specific context.
    // This is key in case you have a compound component that needs index
    // tracking in separate correlating descendant components (like `Tabs`)
    DescendantContext,
    // If you want to declare a specific index value, you can pass it as the
    // third argument here. This is almost never needed but we provide it as an
    // escape hatch for special circumstances.
    explicitIndex
  );

  // Now we know the index, so let's use it!
  let isSelected = index === activeIndex;
  function select() {
    if (!isSelected) {
      setActiveIndex(index);
    }
  }

  return (
    <div
      role="menuitem"
      ref={ref}
      data-selected={isSelected ? "" : undefined}
      tabIndex={-1}
      onMouseEnter={select}
      {...props}
    />
  );
}
```

You can also access the descendants object anywhere in the tree (below the top-level component) with `useDescendants`:

```jsx
let menuItems = useDescendants(DescendantContext);
```

The key tradeoff here is that descendants won't be available on the first render, and as such any components that need this data for server-side rendering will need to manage their own state and pass descendant data from from the top of the tree. For example

```jsx
function Comp() {
  <Listbox>
    {/*
    The button needs to know which value is selected to render its label!
    The label will be empty on the server if we depend on descendant hooks
    */}
    <ListboxButton />
    <ListboxList>
      <ListboxOption value="Apple" />
      <ListboxOption value="Orange" />
      <ListboxOption value="Banana" />
    </ListboxList>
  </Listbox>;
}

function CompSSR() {
  // This limits composition, but now you have your data in one place at the top
  let options = ["Apple", "Orange", "Banana"];
  let [activeOption, setActiveOption] = useState(options[0]);
  <Listbox onChange={setActiveOption} selected={activeOption}>
    {/* The button needs to know which value is selected to render its label! */}
    <ListboxButton>{activeOption}</ListboxButton>
    <ListboxList>
      {options.map((option) => (
        <ListboxOption value={option} key={option} />
      ))}
    </ListboxList>
  </Listbox>;
}

function ComposableSSR() {
  // You can manage state at the top and still get back some composition, you'll
  // just have to deal with a bit of repitition
  let [activeOption, setActiveOption] = useState("Apple");
  <Listbox onChange={setActiveOption} selected={activeOption}>
    {/* The button needs to know which value is selected to render its label! */}
    <ListboxButton>{activeOption}</ListboxButton>
    <ListboxList>
      <ListboxOption value="Apple">
        Apple <span aria-hidden>🍎</span>
      </ListboxOption>
      <ListboxOption
        value="Orange"
        aria-labelledby="orange-label"
        aria-describedby="orange-description"
      >
        <span id="orange-label">
          Orange <span aria-hidden>🍊</span>
        </span>
        <span id="orange-description">Fun fact: Oranges are delicious!</span>
      </ListboxOption>
      <ListboxOption value="Banana">
        Banana <span aria-hidden>🍌</span>
      </ListboxOption>
    </ListboxList>
  </Listbox>;
}
```
