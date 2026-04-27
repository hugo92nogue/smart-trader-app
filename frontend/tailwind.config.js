const { fontFamily } = require("tailwindcss/defaultTheme");

module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{js,tsx,javascript,typescript}"],
  theme: {
    extend: {},
  },
  plugins: [require("tailwindcss-animate")],
};
