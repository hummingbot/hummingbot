# hummingbot-docs
The official documentation for Hummingbot

## Prequisites

The Hummingbot documentation uses [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) as the documentation engine, which renders Markdown files in the `/docs` directory into the documentation site hosted at https://docs.hummingbot.io.

The live site uses the [Insiders build](https://squidfunk.github.io/mkdocs-material/insiders/) - see [installation instructions](https://squidfunk.github.io/mkdocs-material/insiders/getting-started/).

```bash
# set Github personal access token as environment variable
export GH_TOKEN={GH_TOKEN}

# install mkdocs-material (insiders build)
pip install git+https://${GH_TOKEN}@github.com/squidfunk/mkdocs-material-insiders.git

# generate local docs site
mkdocs serve
```

Afterwards, go to `http://localhost:8000` in your web browser.

## Contributions

We welcome contributions by our community! 

Each documentation page contains an pencil icon that allows you suggest edits. Afterwards, please submit a [pull request](https://github.com/CoinAlpha/hummingbot/pulls) with the proposed change and add the **documentation** label.