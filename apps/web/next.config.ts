import type { NextConfig } from "next";

const apiOrigin = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const awsRegion = (process.env.AWS_REGION ?? "us-east-1").replace(/[^a-z0-9-]/gi, "") || "us-east-1";
// Presigned uploads go straight to S3. connect-src must name that host or the
// browser blocks the PUT and the file never reaches the bucket.
const s3Connect = [
  "https://s3.amazonaws.com",
  `https://s3.${awsRegion}.amazonaws.com`,
  `https://*.s3.${awsRegion}.amazonaws.com`,
].join(" ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async headers() {
    const csp = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.clerk.accounts.dev https://*.clerk.com https://challenges.cloudflare.com",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https://img.clerk.com",
      `connect-src 'self' ${apiOrigin} ${s3Connect} https://*.clerk.accounts.dev https://*.clerk.com https://api.clerk.com`,
      "frame-src https://*.clerk.accounts.dev https://*.clerk.com https://challenges.cloudflare.com",
      "worker-src 'self' blob:",
      "font-src 'self' data:",
    ].join("; ");
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  turbopack: {
    // Exact package name only. An absolute filesystem path is treated as a
    // server-relative import (`/workspace/...`), which Turbopack rejects.
    resolveAlias: {
      "pdfjs-dist": "pdfjs-dist/build/pdf.min.mjs",
    },
  },
  webpack: (config) => {
    // pdfjs-dist's unminified build declares a top-level `var __webpack_exports__`, which
    // shadows the dev-mode module wrapper's parameter and crashes on load. The minified
    // build is the same code without those names. `$` keeps the alias to the bare import.
    config.resolve.alias = {
      ...config.resolve.alias,
      "pdfjs-dist$": "pdfjs-dist/build/pdf.min.mjs",
    };
    return config;
  },
};

export default nextConfig;
