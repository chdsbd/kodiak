# Kodiak Docs

The docs site uses <https://docusaurus.io/>.

For the most part content is created with markdown and placed in the `docs/`
folder. Some pages like the `index.html` and the help page require editing
React based code.

## Adding a New Page

Add another markdown file to the `docs/` folder and update the
`sidebars.json` with the new doc's id.

## Dev

```shell
# docs/
yarn install
s/dev
s/typecheck --watch
s/fmt
AGOLIA_API_KEY= AGOLIA_INDEX_NAME= yarn build
```
