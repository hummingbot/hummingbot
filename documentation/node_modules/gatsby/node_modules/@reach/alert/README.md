# @reach/alert

[![Stable release](https://img.shields.io/npm/v/@reach/alert.svg)](https://npm.im/@reach/alert) ![MIT license](https://badgen.now.sh/badge/license/MIT)

[Docs](https://reacttraining.com/reach-ui/alert) | [Source](https://github.com/reach/reach-ui/tree/master/packages/alert) | [WAI-ARIA](https://www.w3.org/TR/wai-aria-practices-1.2/#alert)

Screen-reader-friendly alert messages. In many apps developers add "alert" messages when network events or other things happen. Users with assistive technologies may not know about the message unless you develop for it.

The Alert component will announce to assistive technologies whatever you render to the screen. If you don't have a screen reader on you won't notice a difference between rendering `<Alert>` vs. a `<div>`.

```jsx
function Example(props) {
  const [messages, setMessages] = React.useState([]);
  return (
    <div>
      <button
        onClick={() => {
          setMessages(prevMessages =>
            prevMessages.concat([`Message #${prevMessages.length + 1}`])
          );
          setTimeout(() => {
            setMessages(prevMessages => prevMessages.slice(1));
          }, 5000);
        }}
      >
        Add a message
      </button>
      <div>
        {messages.map((message, index) => (
          <Alert key={index}>{message}</Alert>
        ))}
      </div>
    </div>
  );
}
```
