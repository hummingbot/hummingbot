# Open Collective postinstall

[![Greenkeeper badge](https://badges.greenkeeper.io/opencollective/opencollective-postinstall.svg)](https://greenkeeper.io/)

Lightweight npm postinstall message to invite people to donate to your collective

## Installation

```
npm install --save opencollective-postinstall
```

And in your `package.json` add:

```json
{
  ...
  "scripts": {
    "postinstall": "opencollective-postinstall"
  },
  "collective": {
    "url": "https://opencollective.com/webpack"
  }
  ...
}
```

## Disabling this message

In some places (e.g. CI) you may want to disable this output. You can do this by setting the environment variable `DISABLE_OPENCOLLECTIVE=true`.

It will not be shown if npm's log level is set to silent (`--silent`), warn (`--quiet`), or error (`--loglevel error`).

Note: This is a lightweight alternative to the [opencollective-cli](https://github.com/opencollective/opencollective-cli) that offers a more complete postinstall message with the current balance and ASCII logo of the collective.
