# gatsby-source-git

Source plugin for pulling files into the Gatsby graph from abitrary Git repositories (hosted anywhere). This is useful if the markdown files you wish to render can't live within your gatsby codebase, or if need to aggregate content from disparate repositories.

It clones the repo(s) you configure (a shallow clone, into your cache folder if
you're interested), and then sucks the files into the graph as `File` nodes, as
if you'd configured
[`gatsby-source-filesystem`](https://www.gatsbyjs.org/packages/gatsby-source-filesystem/)
on that directory. As such, all the tranformer plugins that operate on files
should work exactly as they do with `gatsby-source-filesystem` eg with
`gatsby-transformer-remark`, `gatsby-transformer-json` etc.

The only difference is that the `File` nodes created by this plugin will
also have a `gitRemote` field, which will provide you with various bits of
Git related information. The fields on the `gitRemote` node are
mostly provided by
[IonicaBazau/git-url-parse](https://github.com/IonicaBizau/git-url-parse), with
the addition of `ref` and `weblink` fields, which are
the 2 main things you probably want if you're constructing "edit on github"
style links.

N.B. Although with respect to sourcing this works as a drop-in replacement for `gatsby-source-filesystem`, there are a number of helpers included in that module (`createFilePath`, `createRemoteFileNode`, `createFileNodeFromBuffer`) that are not duplicated here – but you can still import and use them from there as needed.

## Requirements

Requires [git](http://git-scm.com/downloads) to be installed, and to be callable using the command `git`.

Ideally we'd use [nodegit](https://github.com/nodegit/nodegit), but it doesn't support shallow clones (see [libgit2/libgit2#3058](https://github.com/libgit2/libgit2/issues/3058)) which would have a significant effect on build times if you wanted to read files from git repositories with large histories.

## Install

`npm install --save gatsby-source-git`

## Configuration

### Plugin options

- `name`: A machine name label for each plugin instance.
- `remote`: The url to clone from.
- `branch` (optional): The branch to use. If none supplied, we try to use the
  'default' branch.
- `patterns` (optional): Passed to
  [fast-glob](https://github.com/mrmlnc/fast-glob) to determine which files get
  sucked into the graph.
- `local` (optional): Specify the local path for the cloned repo. If omitted,
  it will default to a directory within the local Gatsby cache. Note that using
  a location outside the cache will prevent you changing the branch via
  gatsby-config.js. You will need to synchronise the branch of the local
  checkout yourself. However if clones are painful and slow for you, then using
  a custom location will prevent your local repo getting trashed when Gatsby
  clears the cache, which should help.

### Example gatsby-config.js

```javascript
module.exports = {
  plugins: [
    // You can have multiple instances of this plugin to read source files from
    // different repositories or locations within a repository.
    {
      resolve: `gatsby-source-git`,
      options: {
        name: `repo-one`,
        remote: `https://bitbucket.org/stevetweeddale/markdown-test.git`,
        branch: `develop`,
        // Only import the docs folder from a codebase.
        patterns: `docs/**`
      }
    },
    {
      resolve: `gatsby-source-git`,
      options: {
        name: `repo-two`,
        remote: `https://bitbucket.org/stevetweeddale/markdown-test.git`,
        // Specify the local checkout location, to avoid it being trashed on
        // cache clears.
        local: '/explicit/path/to/repo-two',
        // Multiple patterns and negation supported. See https://github.com/mrmlnc/fast-glob
        patterns: [`*`, `!*.md`]
      }
    }
  ]
};
```

This will result in `File` nodes being put in your data graph, it's then up to you to do whatever it is you want to do with that data.

### Private repositories

Most git hosting providers support authentication via URL, either in the form of username and password or more commonly access tokens. So to use a private github repository as an example, you would firstly [generate a personal access token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line). Now you don't want that in your repo, so instead you'd [set an OS environment variable](https://www.gatsbyjs.org/docs/environment-variables/#server-side-nodejs) and then read that environment variable into your plugin config something like:

```javascript
{
  resolve: `gatsby-source-git`,
  options: {
    name: `my-repo`,
    remote: `https://myuser:${process.env.GITHUB_TOKEN}@github.com/myuser/my-repo`,
  },
}
```

## How to query

You can query file nodes exactly as you would node query for nodes created with
[`gatsby-source-filesystem`](https://www.gatsbyjs.org/packages/gatsby-source-filesystem/),
eg:

```graphql
{
  allFile {
    edges {
      node {
        extension
        dir
        modifiedTime
      }
    }
  }
}
```

Similarly, you can filter by the `name` you specified in the config by using
`sourceInstanceName`:

```graphql
{
  allFile(filter: { sourceInstanceName: { eq: "repo-one" } }) {
    edges {
      node {
        extension
        dir
        modifiedTime
      }
    }
  }
}
```

And access some information about the git repo:

```graphql
{
  allFile {
    edges {
      node {
        gitRemote {
          webLink
          ref
        }
      }
    }
  }
}
```

## Creating pages

If you want to programatically create pages on your site from the files in your git repo, you should be able to follow the standard examples, such as [part 7 of the Gatsby tutorial](https://www.gatsbyjs.org/tutorial/part-seven/) or [the standard docs page](https://www.gatsbyjs.org/docs/creating-and-modifying-pages/#creating-pages-in-gatsby-nodejs).
