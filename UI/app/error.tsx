/**
 * Error — Next.js error boundary component for unhandled runtime errors.
 *
 * This is a special Next.js file convention.  When an unhandled error is thrown
 * in any child component, Next.js catches it and renders this component instead
 * of crashing the entire page.  It must be a Client Component ('use client')
 * because error boundaries rely on React's class-based `componentDidCatch`
 * lifecycle, which only works on the client.
 *
 * Props:
 * - `error`: The caught Error object (may include a `digest` for server errors).
 * - `reset`: A function provided by Next.js that re-renders the errored segment,
 *   allowing the user to retry without a full page reload.
 */
'use client';

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Log the error to the browser console whenever the error object changes.
  // In production, this could be replaced with a remote error reporting service
  // (e.g. Sentry, Datadog) for monitoring.
  useEffect(() => {
    console.error('Unhandled error:', error);
  }, [error]);

  return (
    // Full-viewport centered error message matching the app's design system
    <div className="flex h-screen w-full items-center justify-center bg-slate-50">
      <div className="text-center max-w-md px-6">
        <h2 className="text-2xl font-bold text-slate-800 mb-2">
          Something went wrong
        </h2>
        {/* Display the error message if available, otherwise show a generic fallback */}
        <p className="text-sm text-slate-500 mb-6">
          {error.message || 'An unexpected error occurred.'}
        </p>
        {/* Clicking this button calls Next.js's reset() to re-render the errored
            route segment, effectively retrying the operation that failed. */}
        <button
          onClick={reset}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
