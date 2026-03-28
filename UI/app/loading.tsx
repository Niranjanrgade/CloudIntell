/**
 * Loading — Next.js Suspense fallback displayed during page transitions.
 *
 * When Next.js navigates between routes, this component is shown automatically
 * while the new page's data and components are being loaded.  It renders a
 * full-screen centered spinner with an indigo accent color matching the app's
 * design system.
 *
 * This is a special Next.js file convention — placing `loading.tsx` in the
 * `app/` directory makes it the default Suspense boundary for all routes.
 */
export default function Loading() {
  return (
    // Full-viewport centered container with the app's slate background
    <div className="flex h-screen w-full items-center justify-center bg-slate-50">
      <div className="flex flex-col items-center gap-4">
        {/* CSS-only spinner: a circle with a transparent top border that rotates */}
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-indigo-600" />
        <p className="text-sm text-slate-500">Loading...</p>
      </div>
    </div>
  );
}
