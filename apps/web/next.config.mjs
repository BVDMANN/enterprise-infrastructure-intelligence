/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The API URL is public configuration (no secret).
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
};

export default nextConfig;
