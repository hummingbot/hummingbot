import React, { Fragment, createContext, useContext } from "react";
import PropTypes from "prop-types";
import rehypeReact from "rehype-react";
import styled from "@emotion/styled";
import { MDXProvider } from "@mdx-js/react";
import MDXRenderer from "gatsby-plugin-mdx/mdx-renderer";
import { graphql, navigate } from "gatsby";
import { Link } from "react-scroll";
import { ContentWrapper, colors, smallCaps } from "gatsby-theme-apollo-core";
import CodeBlock from "gatsby-theme-apollo-docs/src/components/code-block";
import CustomSEO from "gatsby-theme-apollo-docs/src/components/custom-seo";
import Footer from "gatsby-theme-apollo-docs/src/components/footer";
import PageHeader from "gatsby-theme-apollo-docs/src/components/page-header";
import PageContent from "./page-content";
import { HEADER_HEIGHT } from "gatsby-theme-apollo-docs/src/utils";

const StyledContentWrapper = styled(ContentWrapper)({
  paddingBottom: 0,
});

const CustomLinkContext = createContext();

function CustomLink(props) {
  const { pathPrefix, baseUrl } = useContext(CustomLinkContext);

  const linkProps = { ...props };
  if (props.href) {
    if (props.href.startsWith("/")) {
      linkProps.onClick = function handleClick(event) {
        const href = event.target.getAttribute("href");
        if (href.startsWith("/")) {
          event.preventDefault();
          navigate(href.replace(pathPrefix, ""));
        }
      };
    } else if (!props.href.startsWith("#") && !props.href.startsWith(baseUrl)) {
      linkProps.target = "_blank";
      linkProps.rel = "noopener noreferrer";
    }
  }

  // eslint-disable-next-line
  return <a {...linkProps} alt={"custom link"} aria-label="custom link" />;
}

CustomLink.propTypes = {
  href: PropTypes.string,
};

export const TableWrapper = styled.div({
  overflow: "auto",
  marginBottom: "1.45rem",
});

const tableBorder = `1px solid ${colors.divider}`;
export const StyledTable = styled.table({
  border: tableBorder,
  borderSpacing: 0,
  borderRadius: 4,
  [["th", "td"]]: {
    padding: 16,
    borderBottom: tableBorder,
  },
  "tbody tr:last-child td": {
    border: 0,
  },
  th: {
    ...smallCaps,
    fontSize: 13,
    fontWeight: "normal",
    color: colors.text2,
    textAlign: "inherit",
  },
  td: {
    verticalAlign: "top",
    p: {
      fontSize: "inherit",
      lineHeight: "inherit",
    },
    code: {
      whiteSpace: "normal",
    },
    "> :last-child": {
      marginBottom: 0,
    },
  },
  "&.field-table": {
    td: {
      h6: {
        fontSize: "inherit",
        lineHeight: "inherit",
        fontWeight: "bold",
        marginBottom: "5px",
      },
      "&:first-child p": {
        fontSize: "14px",
        code: {
          color: colors.tertiary,
        },
      },
    },
    "tr.required td": {
      background: colors.background,
    },
  },
});

function CustomTable(props) {
  return (
    <TableWrapper>
      <StyledTable {...props} />
    </TableWrapper>
  );
}

function createCustomHeading(tag) {
  return ({ children, ...props }) =>
    React.createElement(
      tag,
      props,
      <Link
        className="headingLink hello"
        to={props.id}
        spy={true}
        offset={-1 * HEADER_HEIGHT}
        duration={100}
        ignoreCancelEvents={false}
      >
        {Array.isArray(children)
          ? children.filter(
              (child) =>
                child.type !== CustomLink && child.props?.mdxType !== "a"
            )
          : children}
      </Link>
    );
}

const components = {
  pre: CodeBlock,
  a: CustomLink,
  table: CustomTable,
  h1: createCustomHeading("h1"),
  h2: createCustomHeading("h2"),
  h3: createCustomHeading("h3"),
  h4: createCustomHeading("h4"),
  h5: createCustomHeading("h5"),
  h6: createCustomHeading("h6"),
};

const renderAst = new rehypeReact({
  createElement: React.createElement,
  components,
}).Compiler;

export default function Template(props) {
  const { hash, pathname } = props.location;
  const { file, site } = props.data;
  const { frontmatter, headings, fields } =
    file.childMarkdownRemark || file.childMdx;
  const { title, description } = site.siteMetadata;
  const {
    sidebarContents,
    githubUrl,
    spectrumUrl,
    twitterHandle,
    baseUrl,
    ffWidgetId,
  } = props.pageContext;

  const pages = sidebarContents
    .reduce((acc, { pages }) => acc.concat(pages), [])
    .filter((page) => !page.anchor);

  return (
    <Fragment>
      <CustomSEO
        title={frontmatter.title}
        description={frontmatter.description || description}
        siteName={title}
        baseUrl={baseUrl}
        image={fields.image}
        twitterHandle={twitterHandle}
      />
      <StyledContentWrapper>
        <PageHeader {...frontmatter} />
        <hr />
        <PageContent
          title={frontmatter.title}
          apiReference={fields.apiReference}
          pathname={pathname}
          pages={pages}
          headings={headings.filter(
            (heading) =>
              heading.depth === 2 ||
              heading.depth === (fields.apiReference ? 4 : 3)
          )}
          hash={hash}
          githubUrl={githubUrl}
          spectrumUrl={spectrumUrl}
          ffWidgetId={ffWidgetId}
        >
          <CustomLinkContext.Provider
            value={{
              pathPrefix: site.pathPrefix,
              baseUrl,
            }}
          >
            {file.childMdx ? (
              <MDXProvider components={components}>
                <MDXRenderer>{file.childMdx.body}</MDXRenderer>
              </MDXProvider>
            ) : (
              renderAst(file.childMarkdownRemark.htmlAst)
            )}
          </CustomLinkContext.Provider>
        </PageContent>
        <Footer />
      </StyledContentWrapper>
    </Fragment>
  );
}

Template.propTypes = {
  data: PropTypes.object.isRequired,
  pageContext: PropTypes.object.isRequired,
  location: PropTypes.object.isRequired,
};

export const pageQuery = graphql`
  query CustomPageQuery($id: String) {
    site {
      pathPrefix
      siteMetadata {
        title
        description
      }
    }
    file(id: { eq: $id }) {
      childMarkdownRemark {
        frontmatter {
          title
          description
        }
        headings {
          value
          depth
        }
        fields {
          image
          apiReference
        }
        htmlAst
      }
      childMdx {
        frontmatter {
          title
          description
        }
        headings {
          value
          depth
        }
        fields {
          image
          apiReference
        }
        body
      }
    }
  }
`;
