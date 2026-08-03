import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

  turbopack: {
    /**
     * Pin the workspace root to this directory.
     *
     * There is a stray `package-lock.json` in the user's home directory, and
     * with more than one lockfile in the ancestry Next.js infers the root by
     * picking one — it was choosing `C:\Users\<user>`, which makes the
     * standalone build trace files from the entire home directory. Setting this
     * explicitly is the documented fix and does not depend on deleting a
     * lockfile that belongs to something else.
     */
    root: path.resolve(import.meta.dirname),
  },
};

export default nextConfig;
