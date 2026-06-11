/**
 * tailwind.config.js — build estatico del CSS para servir local (sin CDN).
 *
 * Por que existe: algunas redes corporativas bloquean cdn.tailwindcss.com (407 proxy),
 * asi que el Play CDN dejaba la app sin estilos. Buildeamos un CSS con el CLI
 * standalone escaneando templates + JS, y lo servimos desde /static/tailwind.css.
 *
 * Rebuild:
 *   uv run python scripts/build_css.py
 * (baja el CLI standalone de Tailwind y regenera ikigai/static/tailwind.css.
 *  El binario del CLI no se commitea.)
 *
 * Paleta del proyecto (tema tulipan 🌷):
 *   brand   = accion primaria / links (rosa-magenta)
 *   accent  = resaltado (ambar)
 *   success = verde · danger = rojo · ink = grises neutros
 */
module.exports = {
  content: [
    "./ikigai/templates/**/*.j2",
    "./ikigai/static/**/*.js",
    "./ikigai/**/*.py",
  ],
  theme: {
    extend: {
      colors: {
        brand:   { 10: "#fdeef6", 100: "#d81b76", 110: "#c01568", 130: "#8f0f4d" },
        accent:  { 10: "#fff8ec", 100: "#f59e0b", 110: "#e08c08", 140: "#7c4a06" },
        success: { 10: "#effdf3", 100: "#16a34a", 110: "#15803d" },
        danger:  { 10: "#fef2f2", 100: "#dc2626" },
        ink:     { 5: "#f7f7f7", 10: "#f0f0f0", 50: "#cfd3d6", 100: "#74767c", 120: "#5b5e64", 160: "#1d1d1d" },
      },
    },
  },
};
