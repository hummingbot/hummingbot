import React from "react";

export default props =>
  React.createElement("pre", null, JSON.stringify(props, null, 2));
