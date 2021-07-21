import { graphql, useStaticQuery } from "gatsby";

export default function useSiteMetadata() {
  const { site } = useStaticQuery(graphql`
    {
      site {
        siteMetadata {
          description
          discordUrl
          headerButtonLink
          headerButtonText
          siteName
          title
        }
      }
    }
  `);

  return site.siteMetadata;
}
