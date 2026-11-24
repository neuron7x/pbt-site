// Статичний аналіз web/js. Правила — з офіційних наборів: @eslint/js recommended (OpenJS Foundation)
// і eslint-plugin-no-unsanitized (Mozilla) — заборона розбору HTML-рядків у DOM (innerHTML, insertAdjacentHTML, document.write).
import js from '@eslint/js';
import globals from 'globals';
import nounsanitized from 'eslint-plugin-no-unsanitized';

export default [
  js.configs.recommended,
  nounsanitized.configs.recommended,
  {
    files: ['**/*.js'],
    languageOptions: { ecmaVersion: 2022, sourceType: 'script', globals: { ...globals.browser, module: 'readonly' } },
    linterOptions: { reportUnusedDisableDirectives: 'error' },
    rules: {
      strict: ['error', 'function'],
      'no-implicit-globals': 'error',
      'no-var': 'error',
      'prefer-const': 'error',
      eqeqeq: ['error', 'smart'],
      'no-shadow': 'error',
      'no-unused-vars': ['error', { args: 'none' }],
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
      'no-script-url': 'error',
      'no-restricted-properties': ['error',
        { property: 'innerHTML', message: 'Будуйте DOM через el()/textContent — не HTML-рядком.' },
        { property: 'outerHTML', message: 'Будуйте DOM через el()/textContent — не HTML-рядком.' }],
    },
  },
];
