/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    // To use next/image for politician headshots, whitelist host domains here, e.g.:
    // remotePatterns: [{ protocol: "https", hostname: "**.toronto.ca" }],
  },
};

module.exports = nextConfig;
