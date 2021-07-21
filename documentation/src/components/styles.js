import React from "react";
import Icons from "./components-icons/CalloutIcons";

export const Colors = {
  success: {
    heading: "SUCCESS:",
    color: "#0D999E",
    backgroundColor: "#E7F5F5",
    borderColor: "#0D999E",
    icon: <Icons type="success" />,
  },
  danger: {
    heading: "DANGER:",
    color: "#D42B21",
    backgroundColor: "#FBEAE9",
    borderColor: "#D42B21",
    icon: <Icons type="danger" />,
  },
  warning: {
    heading: "WARNING:",
    color: "#F08727",
    backgroundColor: "#FEF3E9",
    borderColor: "#F08727",
    icon: <Icons type="warning" />,
  },
  info: {
    heading: "INFO:",
    color: "#007BBD",
    backgroundColor: "#E6F2F8",
    borderColor: "#007BBD",
    icon: <Icons type="info" />,
  },
  bug: {
    heading: "BUG:",
    color: "#B86A00",
    backgroundColor: "#F8F0E6 ",
    borderColor: "#B86A00",
    icon: <Icons type="bug" />,
  },
  note: {
    heading: "NOTE: ",
    color: "#767676",
    backgroundColor: "#F1F1F1",
    borderColor: "#767676",
    icon: <Icons type="note" />,
  },
  tip: {
    heading: "TIP: ",
    color: "#7153C6",
    backgroundColor: "#F1EEF9",
    borderColor: "#7153C6",
    icon: <Icons type="tip" />,
  },
};

export const Styles = (type) => ({
  borderLeft: "5px solid ",
  marginBottom: "20px",
  borderRadius: "4px",
  color: Colors[type].color,
  backgroundColor: Colors[type].backgroundColor,
  borderColor: Colors[type].borderColor || "black",
});
