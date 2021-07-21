# screenfull.js

> Simple wrapper for cross-browser usage of the JavaScript [Fullscreen API](https://developer.mozilla.org/en/DOM/Using_full-screen_mode), which lets you bring the page or any element into fullscreen. Smoothens out the browser implementation differences, so you don't have to.

**This package is feature complete. No new changes will be accepted.**

---

<p align="center"><b>🔥 Want to strengthen your core JavaScript skills and master ES6?</b><br>I would personally recommend this awesome <a href="https://ES6.io/friend/AWESOME">ES6 course</a> by Wes Bos.</p>

---

### [Demo](https://sindresorhus.com/screenfull.js)

### [Check out my other projects](https://github.com/sindresorhus?tab=repositories)


## Install

Only 0.7 kB gzipped.

Download the [production version][min] or the [development version][max].

[min]: https://github.com/sindresorhus/screenfull.js/raw/gh-pages/dist/screenfull.min.js
[max]: https://github.com/sindresorhus/screenfull.js/raw/gh-pages/dist/screenfull.js

```
$ npm install screenfull
```

Also available on [cdnjs](https://cdnjs.com/libraries/screenfull.js).


## Why?

### Screenfull

```js
if (screenfull.enabled) {
	screenfull.request();
}
```

### Vanilla JavaScript

```js
document.fullscreenEnabled = document.fullscreenEnabled || document.mozFullScreenEnabled || document.documentElement.webkitRequestFullScreen;

function requestFullscreen(element) {
	if (element.requestFullscreen) {
		element.requestFullscreen();
	} else if (element.mozRequestFullScreen) {
		element.mozRequestFullScreen();
	} else if (element.webkitRequestFullScreen) {
		element.webkitRequestFullScreen(Element.ALLOW_KEYBOARD_INPUT);
	}
}

if (document.fullscreenEnabled) {
	requestFullscreen(document.documentElement);
}

// Actually it's more if you want it to work in Safari, but let's not go there...
```


## Support

[Supported browsers](http://caniuse.com/fullscreen)

**Note:** In order to use this package in Internet Explorer, you need a [`Promise` polyfill](https://github.com/stefanpenner/es6-promise).

iPhone is not supported.


## Documentation

### Examples

#### Fullscreen the page

```js
document.getElementById('button').addEventListener('click', () => {
	if (screenfull.enabled) {
		screenfull.request();
	} else {
		// Ignore or do something else
	}
});
```

#### Fullscreen an element

```js
const el = document.getElementById('target');

document.getElementById('button').addEventListener('click', () => {
	if (screenfull.enabled) {
		screenfull.request(el);
	}
});
```

#### Fullscreen an element with jQuery

```js
const target = $('#target')[0]; // Get DOM element from jQuery collection

$('#button').on('click', () => {
	if (screenfull.enabled) {
		screenfull.request(target);
	}
});
```

#### Toggle fullscreen on a image with jQuery

```js
$('img').on('click', event => {
	if (screenfull.enabled) {
		screenfull.toggle(event.target);
	}
});
```

#### Detect fullscreen change

```js
if (screenfull.enabled) {
	screenfull.on('change', () => {
		console.log('Am I fullscreen?', screenfull.isFullscreen ? 'Yes' : 'No');
	});
}
```

Remove listeners with:

```js
screenfull.off('change', callback);
```

#### Detect fullscreen error

```js
if (screenfull.enabled) {
	screenfull.on('error', event => {
		console.error('Failed to enable fullscreen', event);
	});
}
```

See the [demo](https://sindresorhus.com/screenfull.js) for more examples, and view the source.

#### Fullscreen an element with Angular.js

You can use the [Angular.js binding](https://github.com/hrajchert/angular-screenfull) to do something like:

```html
<div ngsf-fullscreen>
	<p>This is a fullscreen element</p>
	<button ngsf-toggle-fullscreen>Toggle fullscreen</button>
</div>
```

#### Fullscreen the page with Angular 2

```typescript
import {Directive, HostListener} from '@angular/core';
import screenfull = require('screenfull');

@Directive({
	selector: '[toggleFullscreen]'
})
export class ToggleFullscreenDirective {
	@HostListener('click') onClick() {
		if (screenfull.enabled) {
			screenfull.toggle();
		}
	}
}
```

```html
<button toggleFullscreen>Toggle fullscreen<button>
```

### Methods

#### .request()

Make an element fullscreen.

Accepts a DOM element. Default is `<html>`. If called with another element than the currently active, it will switch to that if it's a decendant.

If your page is inside an `<iframe>` you will need to add a `allowfullscreen` attribute (+ `webkitallowfullscreen` and `mozallowfullscreen`).

Keep in mind that the browser will only enter fullscreen when initiated by user events like click, touch, key.

Returns a promise that resolves after the element enters fullscreen.

#### .exit()

Brings you out of fullscreen.

Returns a promise that resolves after the element exits fullscreen.

#### .toggle()

Requests fullscreen if not active, otherwise exits.

Returns a promise that resolves after the element enters/exits fullscreen.

#### .on(event, function)

Events: `change` `error`

Add a listener for when the browser switches in and out of fullscreen or when there is an error.

#### .off(event, function)

Remove a previously registered event listener.

#### .onchange(function)

Alias for `.on('change', function)`

#### .onerror(function)

Alias for `.on('error', function)`

### Properties

#### .isFullscreen

Returns a boolean whether fullscreen is active.

#### .element

Returns the element currently in fullscreen, otherwise `null`.

#### .enabled

Returns a boolean whether you are allowed to enter fullscreen. If your page is inside an `<iframe>` you will need to add a `allowfullscreen` attribute (+ `webkitallowfullscreen` and `mozallowfullscreen`).

#### .raw

Exposes the raw properties (prefixed if needed) used internally: `requestFullscreen`, `exitFullscreen`, `fullscreenElement`, `fullscreenEnabled`, `fullscreenchange`, `fullscreenerror`


## FAQ

### How can I navigate to a new page when fullscreen?

That's not supported by browsers for security reasons. There is, however, a dirty workaround. Create a seamless iframe that fills the screen and navigate to the page in that instead.

```js
$('#new-page-btn').click(() => {
	const iframe = document.createElement('iframe')

	iframe.setAttribute('id', 'external-iframe');
	iframe.setAttribute('src', 'http://new-page-website.com');
	iframe.setAttribute('frameborder', 'no');
	iframe.style.position = 'absolute';
	iframe.style.top = '0';
	iframe.style.right = '0';
	iframe.style.bottom = '0';
	iframe.style.left = '0';
	iframe.style.width = '100%';
	iframe.style.height = '100%';

	$(document.body).prepend(iframe);
	document.body.style.overflow = 'hidden';
});
```


## Resources

- [Using the Fullscreen API in web browsers](http://hacks.mozilla.org/2012/01/using-the-fullscreen-api-in-web-browsers/)
- [MDN - Fullscreen API](https://developer.mozilla.org/en/DOM/Using_full-screen_mode)
- [W3C Fullscreen spec](http://dvcs.w3.org/hg/fullscreen/raw-file/tip/Overview.html)
- [Building an amazing fullscreen mobile experience](http://www.html5rocks.com/en/mobile/fullscreen/)
