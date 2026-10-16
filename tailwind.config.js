/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./core/templates/**/*.html",
        "./core/**/*.py",
    ],
    theme: {
        extend: {
            colors: {
                renttech: {
                    dark: '#1E1A4D',
                    primary: '#193CB8',
                    lightblue: '#155DFC',
                    offwhite: '#FAFAF9',
                    darktext: '#1C1917',
                }
            }
        },
    },
    plugins: [],
}