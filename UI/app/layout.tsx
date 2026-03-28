/**
 * RootLayout — Top-level Next.js layout wrapping every page.
 *
 * This is a Server Component that defines the <html> and <body> tags once
 * for the entire application.  It loads the Inter font from Google Fonts
 * and applies it globally via the `className` on <body>.
 *
 * `suppressHydrationWarning` is set on both <html> and <body> to prevent
 * React hydration mismatch warnings that can occur when browser extensions
 * modify the DOM before React hydrates (e.g. dark-mode extensions adding
 * attributes to <html>).
 */
import type {Metadata} from 'next';
import { Inter } from 'next/font/google';
import './globals.css'; // Imports Tailwind CSS base styles and any custom global CSS

// Load the Inter variable font with the Latin subset for optimal performance.
// Next.js automatically self-hosts the font and eliminates layout shift.
const inter = Inter({ subsets: ['latin'] });

// Next.js static metadata — used to populate <title> and <meta name="description">
// in the <head> of every page rendered under this layout.
export const metadata: Metadata = {
  title: 'Multi-Agent Architecture',
  description: 'A UI visualizing a multi-agent workflow with Copilot integration',
};

/**
 * RootLayout wraps all page content in a single <html>/<body> shell.
 * The `children` prop is the rendered page component (e.g. app/page.tsx).
 */
export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/* Apply the Inter font family to the entire app via className */}
      <body className={inter.className} suppressHydrationWarning>{children}</body>
    </html>
  );
}
