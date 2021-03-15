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
  settings: {
    react: {
      version: "detect",
    },
  },
  env: {
    browser: true,
  },
  rules: {
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "error",
    "react/jsx-no-useless-fragment": "error",
    "no-restricted-globals": [
      "error",
      "close",
      "closed",
      "status",
      "name",
      "length",
      "origin",
      "event",
    ],
    "react/self-closing-comp": [
      "error",
      {
        component: true,
        html: true,
      },
    ],
    "import/no-duplicates": "error",
    "no-unneeded-ternary": ["error", { defaultAssignment: false }],
    "@typescript-eslint/no-non-null-assertion": "error",
    "@typescript-eslint/await-thenable": "error",
    "@typescript-eslint/no-for-in-array": "error",
    "@typescript-eslint/prefer-as-const": "error",
    "@typescript-eslint/prefer-reduce-type-parameter": "error",
    "init-declarations": ["error", "always"],
    "react/jsx-fragments": "error",
    "no-lonely-if": "error",
    "object-shorthand": ["error", "always"],
    "@typescript-eslint/consistent-type-assertions": [
      "error",
      {
        assertionStyle: "never",
      },
    ],
    "react/jsx-key": ["error", { checkFragmentShorthand: true }],
    "react/no-danger": "error",
    eqeqeq: ["error", "smart"],
  },
}
