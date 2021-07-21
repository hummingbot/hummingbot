import React from "react";
import { render } from "react-dom";
import UserComponent from "__USER_COMPONENT_PATH__";

// const UserComponent = props => React.createElement('div', null, JSON.stringify(props, null, 2))
const renderFn = ($element, node) =>
  render(React.createElement(UserComponent, node), $element);

window.ogRender = renderFn;
