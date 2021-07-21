import React from "react";

export default function Prompt(props) {
  const textColor = "#20a26a";

  const promptStyle = {
    padding: "10px 20px",
    backgroundColor: "#1c1c1c",
  };

  return (
    <div>
      <div style={promptStyle}>
        <font color={textColor}>{props.prompt}</font>
        <br></br>
        <font color={textColor}>{props.response}</font>
      </div>
      <br></br>
      <br></br>
    </div>
  );
}
