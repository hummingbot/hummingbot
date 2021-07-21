/** @jsx jsx */
import { jsx } from "@emotion/core";
import { colors } from "gatsby-theme-apollo-core";
import logo from "../../images/brand-logo.png";

export default function Logo() {
  return (
    <div css={{ display: "flex", alignItems: "center" }}>
      <img src={logo} alt="" css={{ height: 24, width: 24 }} />
      <div css={{ marginLeft: 8, fontWeight: "bold" }}>
        Hummingbot <span css={{ color: colors.primary }}>Docs</span>
      </div>
    </div>
  );
}
