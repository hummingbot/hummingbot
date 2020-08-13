# hummingbot-docs
Docs for hummingbot, the open source crypto market making bot

Read the [contribution guidelines](https://docs.hummingbot.io/community/guide/) before you proceed to edit the documentation.

<b>Prequisites:</b> MKdocs is required before you can edit the docs, go to [MKdocs](https://www.mkdocs.org/) for details.

<b>For Mac users</b> By default, MacOS ships with Python-2, you need to change it to Python3, see [Link](https://dev.to/malwarebo/how-to-set-python3-as-a-default-python-version-on-mac-4jjf)for details.

## Dependencies

After MKDocs have been installed, navigate to <b>Hummingbot>Documentation</b> folder and run the following dependencies:

```
pip install -r requirements.txt
```

## Develop

Run the following command to build Hummingbot Markdown files into HTML and starts a development server to browse the documentation.
```
mkdocs serve
```

Go to `http://localhost:8000`

## Build

After editing, run the following command to build the documentation,

```
mkdocs build
```
