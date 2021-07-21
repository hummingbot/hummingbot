## React Scroll

Component for animating vertical scrolling.

### Install

```js
$ npm install react-scroll
```

### Run

```js
$ npm install
$ npm test
$ npm start
```

### Examples

Checkout examples

Live example

> [Basic](https://codesandbox.io/s/basic-6t84k)

> [Basic-Keydown](https://codesandbox.io/s/l94kv62o4m)

> [Container](https://codesandbox.io/s/3zznv27l5)

> [With-hash](https://codesandbox.io/s/y0zzrk1v1j)

> [With-overflow](https://codesandbox.io/s/l94kv62o4m)

> [Code](https://github.com/fisshy/react-scroll/blob/master/examples/basic/app.js)

```js
$ npm start
```

### Usage

```js
// ES6 Imports
import * as Scroll from 'react-scroll';
import { Link, Element, Events, animateScroll as scroll, scrollSpy, scroller } from 'react-scroll'

// Or Access Link,Element,etc as follows
let Link      = Scroll.Link;
let Element   = Scroll.Element;
let Events    = Scroll.Events;
let scroll    = Scroll.animateScroll;
let scrollSpy = Scroll.scrollSpy;

// ES5
var React  = require('react');
var Scroll = require('react-scroll');

var Link      = Scroll.Link;
var Element   = Scroll.Element;
var Events    = Scroll.Events;
var scroll    = Scroll.animateScroll;
var scrollSpy = Scroll.scrollSpy;

var Section = React.createClass({
  componentDidMount: function() {
    Events.scrollEvent.register('begin', function(to, element) {
      console.log('begin', arguments);
    });

    Events.scrollEvent.register('end', function(to, element) {
      console.log('end', arguments);
    });

    scrollSpy.update();
  },
  componentWillUnmount: function() {
    Events.scrollEvent.remove('begin');
    Events.scrollEvent.remove('end');
  },
  scrollToTop: function() {
    scroll.scrollToTop();
  },
  scrollToBottom: function() {
    scroll.scrollToBottom();
  },
  scrollTo: function() {
    scroll.scrollTo(100);
  },
  scrollMore: function() {
    scroll.scrollMore(100);
  },
  handleSetActive: function(to) {
    console.log(to);
  },
  render: function () {
    return (
      <div>
        <Link activeClass="active" to="test1" spy={true} smooth={true} offset={50} duration={500} onSetActive={this.handleSetActive}>
          Test 1
        </Link>
        <Link activeClass="active" to="test1" spy={true} smooth={true} offset={50} duration={500} delay={1000}>
          Test 2 (delay)
        </Link>
        <Link className="test6" to="anchor" spy={true} smooth={true} duration={500}>
          Test 6 (anchor)
        </Link>
        <Button activeClass="active" className="btn" type="submit" value="Test 2" to="test2" spy={true} smooth={true} offset={50} duration={500} >
          Test 2
        </Button>

        <Element name="test1" className="element">
          test 1
        </Element>

        <Element name="test2" className="element">
          test 2
        </Element>

        <div id="anchor" className="element">
          test 6 (anchor)
        </div>

        <Link to="firstInsideContainer" containerId="containerElement">
          Go to first element inside container
        </Link>

        <Link to="secondInsideContainer" containerId="containerElement">
          Go to second element inside container
        </Link>
        <div className="element" id="containerElement">
          <Element name="firstInsideContainer">
            first element inside container
          </Element>

          <Element name="secondInsideContainer">
            second element inside container
          </Element>
        </div>

        <a onClick={this.scrollToTop}>To the top!</a>
        <br/>
        <a onClick={this.scrollToBottom}>To the bottom!</a>
        <br/>
        <a onClick={this.scrollTo}>Scroll to 100px from the top</a>
        <br/>
        <a onClick={this.scrollMore}>Scroll 100px more from the current position!</a>
      </div>
    );
  }
});

React.render(
  <Section />,
  document.getElementById('example')
);
```

### Props/Options

> activeClass - class applied when element is reached

> to - target to scroll to

> containerId - container to listen for scroll events and to perform scrolling in 

> spy - make Link selected when scroll is at its targets position

> hashSpy - update hash based on spy, containerId has to be set to scroll a specific element.

> smooth - animate the scrolling

> offset - scroll additional px ( like padding )

> duration - time of the scroll animation - can be a number or a function (`function (scrollDistanceInPx) { return duration; }`), that allows more granular control at run-time

> delay - wait x milliseconds before scroll

> isDynamic - in case the distance has to be recalculated - if you have content that expands etc.

> onSetActive - invoke whenever link is being set to active

> onSetInactive - invoke whenever link is lose the active status

> ignoreCancelEvents - ignores events which cancel animated scrolling

```js
<Link activeClass="active"
      to="target"
      spy={true}
      smooth={true}
      hashSpy={true}
      offset={50}
      duration={500}
      delay={1000}
      isDynamic={true}
      onSetActive={this.handleSetActive}
      onSetInactive={this.handleSetInactive}
      ignoreCancelEvents={false}
>
  Your name
</Link>
```

### Scroll Methods

> Scroll To Top

```js
var Scroll = require('react-scroll');
var scroll = Scroll.animateScroll;

scroll.scrollToTop(options);
```

> Scroll To Bottom

```js
var Scroll = require('react-scroll');
var scroll = Scroll.animateScroll;

scroll.scrollToBottom(options);
```

> Scroll To (position)

```js
var Scroll = require('react-scroll');
var scroll = Scroll.animateScroll;

scroll.scrollTo(100, options);
```

> Scroll To (Element)

animateScroll.scrollTo(positionInPixels, props = {});

```js
var Scroll   = require('react-scroll');
var Element  = Scroll.Element;
var scroller = Scroll.scroller;

<Element name="myScrollToElement"></Element>

// Somewhere else, even another file
scroller.scrollTo('myScrollToElement', {
  duration: 1500,
  delay: 100,
  smooth: true,
  containerId: 'ContainerElementID',
  offset: 50, // Scrolls to element + 50 pixels down the page
  ...
})
```

> Scroll More (px)

```js
var Scroll = require('react-scroll');
var scroll = Scroll.animateScroll;

scroll.scrollMore(10, options);
```

### Scroll events

> begin - start of the scrolling

```js
var Scroll = require('react-scroll');
var Events = Scroll.Events;

Events.scrollEvent.register('begin', function(to, element) {
  console.log('begin', to, element);
});
```

> end - end of the scrolling/animation

```js

Events.scrollEvent.register('end', function(to, element) {
  console.log('end', to, element);
});
```

> Remove events

```js
Events.scrollEvent.remove('begin');
Events.scrollEvent.remove('end');
```

#### Create your own Link/Element
> Simply just pass your component to one of the high order components (Element/Scroll)

```js
var React         = require('react');
var Scroll        = require('react-scroll');
var ScrollLink    = Scroll.ScrollLink;
var ScrollElement = Scroll.ScrollElement;

var Element = React.createClass({
  render: function () {
    return (
      <div {...this.props}  ref={(el) => { this.props.parentBindings.domNode = el; }}>
        {this.props.children}
      </div>
    );
  }
});

module.exports = ScrollElement(Element);

var Link = React.createClass({
  render: function () {
    return (
      <a {...this.props}>
        {this.props.children}
      </a>
    );
  }
});

module.exports = ScrollLink(Link);
```

### Scroll Animations
> Add a custom easing animation to the smooth option. This prop will accept a Boolean if you want the default, or any of the animations listed below

```js
scroller.scrollTo('myScrollToElement', {
  duration: 1500,
  delay: 100,
  smooth: 'easeInOutQuint',
  containerId: 'ContainerElementID',
  ...
})
```

> List of currently available animations:

```
linear
	- no easing, no acceleration.
easeInQuad
	- accelerating from zero velocity.
easeOutQuad
	- decelerating to zero velocity.
easeInOutQuad
	- acceleration until halfway, then deceleration.
easeInCubic
	- accelerating from zero velocity.
easeOutCubic
	- decelerating to zero velocity.
easeInOutCubic
	- acceleration until halfway, then deceleration.
easeInQuart
	- accelerating from zero velocity.
easeOutQuart
	- decelerating to zero velocity.
easeInOutQuart
	-  acceleration until halfway, then deceleration.
easeInQuint
	- accelerating from zero velocity.
easeOutQuint
	- decelerating to zero velocity.
easeInOutQuint
	- acceleration until halfway, then deceleration.
```

A good visual reference can be found at [easings.net](http://easings.net/)

#### Changelog
- [See the CHANGELOG](./CHANGELOG.md)
