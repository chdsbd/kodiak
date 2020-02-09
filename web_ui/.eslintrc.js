module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    sourceType: "module",
    project: "./tsconfig.json",
    ecmaFeatures: {
      jsx: true,
    },
  },
  plugins: ["html", "react", "react-hooks", "@typescript-eslint", "import"],
  extends: ["prettier"],
  env: {
    browser: true,
  },
  rules: {
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "error",
    "react/self-closing-comp": ["error", {
      "component": true,
      "html": true
    }],
    "import/no-duplicates": "error",
    'no-unneeded-ternary': ['error', { defaultAssignment: false }],
    '@typescript-eslint/no-non-null-assertion': 'error',
    'init-declarations': ['error', 'always'],
    'react/jsx-fragments': 'error',
    'no-lonely-if': 'error'
  },
}
