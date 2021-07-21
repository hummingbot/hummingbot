'use strict';

function _defineProperty(obj, key, value) { if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }

const React = require('react');

const PropTypes = require('prop-types');

const {
  Box
} = require('ink');

const spinners = require('cli-spinners');

class Spinner extends React.Component {
  constructor(...args) {
    super(...args);

    _defineProperty(this, "state", {
      frame: 0
    });

    _defineProperty(this, "switchFrame", () => {
      const {
        frame
      } = this.state;
      const spinner = this.getSpinner();
      const isLastFrame = frame === spinner.frames.length - 1;
      const nextFrame = isLastFrame ? 0 : frame + 1;
      this.setState({
        frame: nextFrame
      });
    });
  }

  render() {
    const spinner = this.getSpinner();
    return /*#__PURE__*/React.createElement(Box, null, spinner.frames[this.state.frame]);
  }

  componentDidMount() {
    const spinner = this.getSpinner();
    this.timer = setInterval(this.switchFrame, spinner.interval);
  }

  componentWillUnmount() {
    clearInterval(this.timer);
  }

  getSpinner() {
    return spinners[this.props.type] || spinners.dots;
  }

}

_defineProperty(Spinner, "propTypes", {
  type: PropTypes.string
});

_defineProperty(Spinner, "defaultProps", {
  type: 'dots'
});

module.exports = Spinner;
module.exports.default = Spinner;