import PropTypes from "prop-types";
import React, { Fragment, useEffect, useMemo, useRef } from "react";
import styled from "@emotion/styled";
import useKey from "react-use/lib/useKey";
import useWindowSize from "react-use/lib/useWindowSize";
import { boxShadow } from "gatsby-theme-apollo-docs/src/components/search";
import { breakpoints, colors, smallCaps } from "gatsby-theme-apollo-core";
import { size, transparentize } from "polished";
import useSiteMetadata from "../../hooks/useSiteMetadata";
import { ReactComponent as DiscordLogo } from "gatsby-theme-apollo-docs/src/assets/discord.svg";
import { ReactComponent as IconYoutube } from "gatsby-theme-apollo-docs/src/assets/youtube.svg";
import { ReactComponent as IconTwitter } from "gatsby-theme-apollo-docs/src/assets/twitter.svg";
import "katex/dist/katex.min.css";

const Wrapper = styled.div({
  width: "100%",
  height: "100%",
  backgroundColor: transparentize(0.5, colors.text2),
  overflow: "auto",
  position: "fixed",
  top: 0,
  left: 0,
  zIndex: 3,
  perspective: "1000px",
  transitionProperty: "opacity, visibility",
  transitionDuration: "150ms",
  transitionTimingFunction: "ease-in-out",
});

const transitionDuration = 150; // in ms
const Menu = styled.div({
  width: 700,
  marginBottom: 24,
  borderRadius: 4,
  boxShadow,
  backgroundColor: "white",
  overflow: "hidden",
  position: "absolute",
  transformOrigin: "25% 25%",
  transition: `transform ${transitionDuration}ms ease-in-out`,
  outline: "none",
  [breakpoints.md]: {
    width: 450,
  },
  [breakpoints.sm]: {
    width: "calc(100vw - 48px)",
  },
});

const MenuTitle = styled.h6(smallCaps, {
  margin: 24,
  marginBottom: 0,
  fontSize: 13,
  fontWeight: 600,
  color: colors.text3,
});

const StyledNav = styled.nav({
  display: "flex",
  flexWrap: "wrap",
  margin: 12,
});

const NavItem = styled.div({
  display: "block",
  width: "50%",
  [breakpoints.md]: {
    width: "100%",
  },
});

const NavItemInner = styled.a({
  display: "block",
  height: "100%",
  padding: 12,
  borderRadius: 4,
  color: colors.text1,
  textDecoration: "none",
  backgroundColor: "transparent",
  transitionProperty: "color, background-color",
  transitionDuration: "150ms",
  transitionTimingFunction: "ease-in-out",
  "@media (hover: hover)": {
    ":hover": {
      color: "white",
      backgroundColor: colors.primary,
      p: {
        color: colors.primaryLight,
      },
    },
  },
});

export const NavItemTitle = styled.h4({
  marginBottom: 8,
  fontWeight: 600,
  color: "inherit",
});

export const NavItemDescription = styled.p({
  marginBottom: 0,
  fontSize: 14,
  lineHeight: 1.5,
  color: colors.text3,
  transition: "color 150ms ease-in-out",
});

const FooterNav = styled.nav({
  display: "flex",
  alignItems: "center",
  padding: "16px 24px",
  backgroundColor: colors.background,
  [breakpoints.md]: {
    display: "block",
  },
});

const FooterNavItem = styled.a({
  color: colors.text2,
  textDecoration: "none",
  ":hover": {
    color: colors.text3,
  },
  ":not(:last-child)": {
    marginRight: 24,
  },
});

const SocialLinks = styled.div({
  display: "flex",
  marginLeft: "auto",
  [breakpoints.md]: {
    marginTop: 8,
  },
});

const SocialLink = styled.a({
  color: colors.text2,
  ":hover": {
    color: colors.text3,
  },
  ":not(:last-child)": {
    marginRight: 24,
  },
  svg: {
    ...size(24),
    display: "block",
    fill: "currentColor",
  },
});

export default function DocsetSwitcher(props) {
  const menuRef = useRef(null);
  const { width } = useWindowSize();
  useKey("Escape", props.onClose);

  useEffect(() => {
    if (props.open) {
      // focus the menu after it has been transitioned in
      setTimeout(() => {
        menuRef.current.focus();
      }, transitionDuration);
    }
  }, [props.open]);

  const { current } = props.buttonRef;
  const menuStyles = useMemo(() => {
    if (!current) {
      return null;
    }

    const { top, left, height } = current.getBoundingClientRect();
    return {
      top: top + height + 2,
      left,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, width, props.open]);

  function handleWrapperClick(event) {
    if (event.target === event.currentTarget) {
      props.onClose();
    }
  }

  const metadata = useSiteMetadata();

  const hasSocialUrls = Boolean(
    props.twitterUrl || props.youtubeUrl || metadata.discordUrl
  );

  return (
    <Wrapper
      onClick={handleWrapperClick}
      style={{
        opacity: props.open ? 1 : 0,
        visibility: props.open ? "visible" : "hidden",
      }}
    >
      <Menu
        ref={menuRef}
        tabIndex={-1}
        style={{
          ...menuStyles,
          transform:
            !props.open && "translate3d(0,-24px,-16px) rotate3d(1,0,0.1,8deg)",
        }}
      >
        <MenuTitle>{props.siteName}</MenuTitle>
        <StyledNav>
          {props.navItems.map((navItem) => (
            <NavItem key={navItem.url}>
              <NavItemInner href={navItem.url}>
                <NavItemTitle>{navItem.title}</NavItemTitle>
                <NavItemDescription>{navItem.description}</NavItemDescription>
              </NavItemInner>
            </NavItem>
          ))}
        </StyledNav>
        {(props.footerNavConfig || hasSocialUrls) && (
          <FooterNav>
            <Fragment>
              {props.footerNavConfig &&
                Object.entries(props.footerNavConfig).map(([text, props]) => (
                  <FooterNavItem key={text} {...props}>
                    {text}
                  </FooterNavItem>
                ))}
              {hasSocialUrls && (
                <SocialLinks>
                  {metadata.discordUrl && (
                    <SocialLink
                      href={metadata.discordUrl}
                      title="Discord"
                      target="_blank"
                    >
                      <DiscordLogo />
                    </SocialLink>
                  )}
                  {props.twitterUrl && (
                    <SocialLink
                      href={props.twitterUrl}
                      title="Twitter"
                      target="_blank"
                    >
                      <IconTwitter />
                    </SocialLink>
                  )}
                  {props.youtubeUrl && (
                    <SocialLink
                      href={props.youtubeUrl}
                      title="YouTube"
                      target="_blank"
                    >
                      <IconYoutube />
                    </SocialLink>
                  )}
                </SocialLinks>
              )}
            </Fragment>
          </FooterNav>
        )}
      </Menu>
    </Wrapper>
  );
}

DocsetSwitcher.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  buttonRef: PropTypes.object.isRequired,
  siteName: PropTypes.string.isRequired,
  navItems: PropTypes.array.isRequired,
  footerNavConfig: PropTypes.object.isRequired,
  twitterUrl: PropTypes.string,
  youtubeUrl: PropTypes.string,
};
