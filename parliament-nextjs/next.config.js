/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    // Politician headshots are hosted on government domains. If you switch from
    // the plain <img> in components/ui.tsx to next/image, list those hosts here, e.g.:
    // remotePatterns: [{ protocol: "https", hostname: "**.toronto.ca" }, { protocol: "https", hostname: "**.ola.org" }],
  },
};

module.exports = nextConfig;
