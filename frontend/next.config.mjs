import bundleAnalyzer from "@next/bundle-analyzer";

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow CI/verification builds to target a separate dist dir so running
  // `next build` never invalidates the chunks a live `next dev` is serving.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  experimental: {
    optimizePackageImports: ["lucide-react", "@xyflow/react"],
  },
};

export default withBundleAnalyzer(nextConfig);