/** @type {import('next').NextConfig} */
// NOTE: evaluated at BUILD time (standalone output bakes rewrites into the build).
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

module.exports = {
  output: "standalone",
  trailingSlash: true, // Django endpoints end with "/"
  async rewrites() {
    // Same-origin proxy: the httpOnly refresh cookie works without CORS or cross-site cookies.
    // The trailing-slash rule must come first: Next strips the slash from `:path*` otherwise, and Django
    // would answer POSTs with a 301 redirect.
    return [
      { source: "/api/:path*/", destination: `${BACKEND}/api/:path*/` },
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
    ];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ],
    }];
  },
};
