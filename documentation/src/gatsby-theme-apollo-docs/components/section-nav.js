import React, { useState, useEffect } from "react";
import PropTypes from "prop-types";
import styled from "@emotion/styled";
import Slugger from "github-slugger";
import striptags from "striptags";
import cn from "classnames";
import { Link } from "react-scroll";
import useWindowScroll from "react-use/lib/useWindowScroll";
import { colors } from "gatsby-theme-apollo-core";
import { HEADER_HEIGHT } from "gatsby-theme-apollo-docs/src/utils";
import { trackCustomEvent } from "gatsby-plugin-google-analytics";

const StyledList = styled.ul({
  marginLeft: 0,
  marginBottom: 48,
  overflow: "auto",
});

const StyledListItem = styled.li({
  listStyle: "none",
  fontSize: "1rem",
  lineHeight: "inherit",
  "&.active": {
    color: colors.primary,
    fontWeight: "bold",
  },

  a: {
    color: "inherit",
    textDecoration: "none",
    ":hover": {
      opacity: colors.hoverOpacity,
      cursor: "pointer",
    },
    "&.active": {
      color: colors.primary,
      fontWeight: "bold",
    },
  },
});

export default function SectionNav(props) {
  const { y } = useWindowScroll();
  const slugger = new Slugger();
  const { contentRef, imagesLoaded } = props;
  const [offsets, setOffsets] = useState([]);

  useEffect(() => {
    const headings = contentRef.current.querySelectorAll(
      [1, ...props.headings.map((heading) => heading.depth)]
        .map((depth) => "h" + depth)
        .toString()
    );
    setOffsets(
      Array.from(headings)
        .map((heading) => {
          return {
            id: heading.id,
            offset: heading.offsetTop,
          };
        })
        .filter(Boolean)
    );
  }, [contentRef, imagesLoaded, props.headings]);

  let activeHeading = null;
  const scrollTop = y;
  for (let i = offsets.length - 1; i >= 0; i--) {
    const { id, offset } = offsets[i];
    if (scrollTop >= offset - 1.5 * HEADER_HEIGHT) {
      activeHeading = id;
      break;
    }
  }

  const handleHeadingClick = (linkLabel) => {
    trackCustomEvent({
      category: "Section Nav",
      action: "Heading click",
      label: linkLabel,
    });
  };

  return (
    <StyledList>
      {props.headings.map(({ depth, value }) => {
        const text = striptags(value);
        const slug = slugger.slug(text);
        return (
          <StyledListItem
            key={slug}
            style={{ paddingLeft: depth !== 2 && 16 }}
            className={cn({ active: activeHeading === slug })}
          >
            <Link
              activeClass="active"
              to={slug}
              spy={true}
              offset={-1 * HEADER_HEIGHT}
              duration={100}
              ignoreCancelEvents={false}
              onSetActive={(e) => handleHeadingClick(e)}
            >
              {text}
            </Link>
          </StyledListItem>
        );
      })}
    </StyledList>
  );
}

SectionNav.propTypes = {
  headings: PropTypes.array.isRequired,
};
