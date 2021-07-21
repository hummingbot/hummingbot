const resolve = module => require.resolve(module)

exports.onCreateWebpackConfig = (
  { getConfig, actions, stage, loaders },
  { plugins, include, exclude, ...svgrOptions }
) => {
  const { replaceWebpackConfig, setWebpackConfig } = actions
  const existingConfig = getConfig()

  const rules = existingConfig.module.rules.map(rule => {
    if(
      String(rule.test) === String(/\.(ico|svg|jpg|jpeg|png|gif|webp)(\?.*)?$/)
    ) {
      return {
        ...rule,
        test: /\.(ico|jpg|jpeg|png|gif|webp)(\?.*)?$/
      }
    }

    return rule
  })

  replaceWebpackConfig({
    ...existingConfig,
    module: {
      ...existingConfig.module,
      rules
    }
  })

  const urlLoader = loaders.url({ name: 'static/[name].[hash:8].[ext]' })

  // for non-javascript issuers
  const nonJs = {
    test: /\.svg$/,
    use: [urlLoader],
    issuer: {
      test: /\.(?!(js|jsx|ts|tsx)$)([^.]+$)/,
    },
  }

  const svgrLoader = {
    loader: resolve(`@svgr/webpack`),
    options: svgrOptions,
  }
  
  // add new svg rule
  const svgrRule = {
    test: /\.svg$/,
    use: [svgrLoader, urlLoader],
    issuer: {
      test: /\.(js|jsx|ts|tsx)$/
    },
    include,
    exclude
  }
  
  // for excluded assets
  const excludedRule = {
    test: /\.svg$/,
    use: urlLoader,
    issuer: svgrRule.issuer,
    include: exclude,
    exclude: include,
  }

  let configRules = []

  switch (stage) {
    case `develop`:
    case `build-javascript`:
    case `build-html`:
    case `develop-html`:
      if(include || exclude) {
        configRules = configRules.concat([excludedRule])
      }

      configRules = configRules.concat([nonJs, svgrRule])
      break
    default:
  }

  setWebpackConfig({
    module: {
      rules: configRules,
    },
  })
}