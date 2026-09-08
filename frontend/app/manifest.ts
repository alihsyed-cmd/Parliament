import type { MetadataRoute } from "next";

// Icons for home-screen shortcuts and browser install prompts. Display stays
// "browser" to match appleWebApp.capable: false in layout.tsx — the app is meant
// to run with normal browser chrome, on both platforms.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Parliament App",
    short_name: "Parliament",
    description:
      "Meet the people who work for you. Enter your postal code to see your municipal, provincial, and federal representatives.",
    start_url: "/",
    display: "browser",
    background_color: "#f3ead5",
    theme_color: "#fbf7ee",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
