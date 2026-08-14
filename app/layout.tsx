import type { Metadata } from "next";
import type { ReactNode } from "react";
import { MotionConfig } from "motion/react";
import "./globals.css";

export const metadata: Metadata = {
  title: "achilles v0.1.0",
  description:
    "Paste a job description and your resume, get back a tailored, one-page, ATS-scored PDF. Reads like a marked-up proof.",
};

// Mirrors --ease / --dur-2 from app/globals.css. Keep the two in step: every
// motion in the app — CSS transition or motion/react tween — has to come from
// the same hand, and `reducedMotion="user"` makes motion/react honour
// prefers-reduced-motion the way the global CSS block already does.
//
// As of now NOTHING in the tree is a motion component: every animation is CSS,
// which is why this config looks unused. It is the standing guarantee for the
// next one — a component's own `transition` prop REPLACES this default rather
// than merging into it, so anything animating in JS must still pass `ease`
// explicitly. That mistake is exactly what ThinkingTrace shipped with.
const EASE: [number, number, number, number] = [0.23, 1, 0.32, 1];
const DURATION = 0.18;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // Browser extensions (LanguageTool's `data-lt-installed`, Grammarly, dark-mode
    // injectors) mutate <html> before React hydrates, which React reports as an
    // attribute mismatch even though the server markup is correct. This scopes
    // the suppression to attributes on this one element — content mismatches
    // deeper in the tree are still reported.
    <html lang="en" suppressHydrationWarning>
      {/* `mono` is the working voice of the app; prose and headings opt into
          `serif` locally. `tabular` on the body means every figure in every
          table inherits fixed-width digits and columns never jitter. */}
      <body className="mono tabular" suppressHydrationWarning>
        <MotionConfig
          reducedMotion="user"
          transition={{ duration: DURATION, ease: EASE }}
        >
          {children}
        </MotionConfig>
      </body>
    </html>
  );
}
