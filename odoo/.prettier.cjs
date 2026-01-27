/** @type {import('prettier').Config} */

const config = {
    // https://github.com/prettier/prettier/issues/15388#issuecomment-1717746872
    plugins: [require.resolve("@prettier/plugin-xml")],
    bracketSpacing: false,
    printWidth: 88,
    overrides: [
        {
            "files": "**/*.xml",
            "options": {
                "printWidth": 100
            }
        }
    ],
    tabWidth: 4,
    proseWrap: "always",
    semi: true,
    trailingComma: "es5",
    xmlWhitespaceSensitivity: "preserve",
};

module.exports = config;