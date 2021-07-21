<p align="center">
<img src="./resources/logo.png" width="500">
</p>
<p align="center">
 Complex Loader Management for <a href="http://reactjs.org/" rel="nofollow" class="rich-diff-level-one">React</a>.
</p>

<p align="center">
 <strong class="rich-diff-level-one">Read the <a href="https://medium.com/@fkadev/managing-complex-waiting-experiences-on-web-uis-29534d2d92a8" rel="nofollow">Medium post "Managing Complex Waiting Experiences on Web UIs"</a>.</strong>
</p>

<p align="center">
<img src="./resources/react-wait.gif" width="600" />
</p>

[![npm version](https://badge.fury.io/js/react-wait.svg)](https://badge.fury.io/js/react-wait)
[![build](https://api.travis-ci.org/f/react-wait.svg?branch=master)](https://travis-ci.org/f/react-wait)

---

> [Play with Demo](https://codesandbox.io/s/pmp3w1om17).

**react-wait** is a **React Hook** helps to manage multiple loading states on the page without any conflict. It's based on a **very simple idea** that manages a **`Arrayg`** with multiple loading states. The **built-in loader component** listens its registered loader and immediately become loading state.

## **Why not `React.Suspense`?**:

React has its own Suspense feature to manage all the async works. For now it only supports code-splitting (not data-fetching).

`useWait` allows you to manage waiting experiences much more explicitly and **not only for Promised/async patterns but also complete loading management**.

# Overview

Here's a quick overview that what's `useWait` for:

```jsx
import { useWait, Waiter } from "react-wait";

function A() {
  const { isWaiting } = useWait();
  return (
    <div>
      {isWaiting("creating user") ? "Creating User..." : "Nothing happens"}
    </div>
  );
}

function B() {
  const { anyWaiting } = useWait();
  return (
    <div>
      {anyWaiting() ? "Something happening on app..." : "Nothing happens"}
    </div>
  );
}

function C() {
  const { startWaiting, endWaiting, isWaiting } = useWait();

  function createUser() {
    startWaiting("creating user");
    // Faking the async work:
    setTimeout(() => {
      endWaiting("creating user");
    }, 1000);
  }

  return (
    <button disabled={isWaiting("creating user")} onClick={createUser}>
      <Wait on="creating user" fallback={<Spinner />}>
        Create User
      </Wait>
    </button>
  );
}

ReactDOM.render(
  <Waiter>
    <C />
  </Waiter>,
  document.getElementById("root")
);
```

# Quick Start

If you are a **try and learn** developer, you can start trying the **react-wait** now using [codesandbox.io](https://codesandbox.io).

[![Edit useWait](https://codesandbox.io/static/img/play-codesandbox.svg)](https://codesandbox.io/s/pmp3w1om17)

### 1. Install:

```bash
yarn add react-wait
```

### 2. Require:

```jsx
import { Waiter, useWait } from "react-wait";

function UserCreateButton() {
  const { startWaiting, endWaiting, isWaiting, Wait } = useWait();

  return (
    <button
      onClick={() => startWaiting("creating user")}
      disabled={isWaiting("creating user")}
    >
      <Wait on="creating user" fallback={<div>Creating user!</div>}>
        Create User
      </Wait>
    </button>
  );
}
```

### 3. Wrap with the `Waiter` Context Provider

And you should wrap your `App` with `Waiter` component. It's actually a `Context.Provider` that provides a loading context to the component tree.

```jsx
const rootElement = document.getElementById("root");
ReactDOM.render(
  <Waiter>
    <App />
  </Waiter>,
  rootElement
);
```

## Installation

```bash
$ yarn add react-wait
# or if you using npm
$ npm install react-wait
```

## The API

**react-wait** provides some helpers to you to use in your templates.

#### `anyWaiting()`

Returns boolean value if any loader exists in context.

```jsx
const { anyWaiting } = useWait();

return <button disabled={anyWaiting()}>Disabled while waiting</button>;
```

#### `isWaiting(waiter String)`

Returns boolean value if given loader exists in context.

```jsx
const { isWaiting } = useWait();

return (
  <button disabled={isWaiting("creating user")}>
    Disabled while creating user
  </button>
);
```

#### `startWaiting(waiter String)`

Starts the given waiter.

```jsx
const { startWaiting } = useWait();

return <button onClick={() => startWaiting("message")}>Start</button>;
```

#### `endWaiting(waiter String)`

Stops the given waiter.

```jsx
const { end } = useWait();

return <button onClick={() => endWaiting("message")}>Stop</button>;
```

## Using `Wait` Component

```jsx
function Component() {
  const { Wait } = useWait();
  return (
    <Wait on="the waiting message" fallback={<div>Waiting...</div>}>
      The content after waiting done
    </Wait>
  );
}
```

Better example for a `button` with loading state:

```jsx
<button disabled={isWaiting("creating user")}>
  <Wait on="creating user" fallback={<div>Creating User...</div>}>
    Create User
  </Wait>
</button>
```

## Making Reusable Loader Components

With reusable loader components, you will be able to use custom loader components as example below. This will allow you to create better **user loading experience**.

```jsx
function Spinner() {
  return <img src="spinner.gif" />;
}
```

Now you can use your spinner everywhere using `waiting` attribute:

```jsx
<button disabled={isWaiting("creating user")}>
  <Wait on="creating user" fallback={<Spinner />}>
    Create User
  </Wait>
</button>
```

## Creating Waiting Contexts using `createWaitingContext(context String)`

To keep your code DRY you can create a `Waiting Context` using `createWaitingContext`.

```jsx
function CreateUserButton() {
  const { createWaitingContext } = useWait();

  // All methods will be curried with "creating user" on.
  const { startWaiting, endWaiting, isWaiting, Wait } = createWaitingContext(
    "creating user"
  );

  function createUser() {
    startWaiting();
    setTimeout(endWaiting, 1000);
  }

  return (
    <Button disabled={isWaiting()} onClick={createUser}>
      <Wait fallback="Creating User...">Create User</Wait>
    </Button>
  );
}
```

## Contributors

- Fatih Kadir Akın, (creator)

## Other Implementations

Since **react-wait** based on a very simple idea, it can be implemented on other frameworks.

- [vue-wait](https://github.com/f/vue-wait): Multiple Process Loader Management for Vue.
- [dom-wait](https://github.com/f/dom-wait): Multiple Process Loader Management for vanilla JavaScript.

## License

MIT © [Fatih Kadir Akın](https://github.com/f)
