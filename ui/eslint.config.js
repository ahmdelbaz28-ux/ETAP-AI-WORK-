import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    linterOptions: {
      reportUnusedDisableDirectives: "off",
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-hooks/immutability": "off",
      "react-hooks/refs": "off",
      "react-hooks/purity": "off",
      "react-hooks/use-memo": "off",
      "react-hooks/incompatible-library": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/exhaustive-deps": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "no-useless-escape": "off",
      "require-yield": "off",
      "react-refresh/only-export-components": "off",
    },
  },
);
