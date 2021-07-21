import React from "react";

//Simple component for Table Status color and font

export default function StatusCircle(props) {
  const style = {
    color: props.color,
    fontSize: props.font,
  };
  return <span style={style}>⬤</span>;
}
