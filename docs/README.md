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
# /docs/website/
yarn install
yarn start
yarn typecheck --watch
yarn fmt
```
