/**
 * useIsMobile — Responsive breakpoint detection hook.
 *
 * Listens for viewport width changes and returns `true` when the window
 * width is below 768px (mobile breakpoint).  Used for responsive layout
 * adjustments across the application.
 */
import * as React from "react"

// Breakpoint threshold in pixels — viewports narrower than this are considered mobile.
const MOBILE_BREAKPOINT = 768

/**
 * Returns `true` when the viewport width is below the mobile breakpoint (768px).
 *
 * Internally uses `window.matchMedia` to listen for viewport changes rather
 * than polling or attaching a resize listener, which is more performant.
 * The initial value is computed synchronously on mount to avoid a flash of
 * incorrect layout, and subsequent changes trigger a re-render via the
 * matchMedia "change" event.
 */
export function useIsMobile() {
  // undefined initially because we don't know the viewport width during SSR
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)

  React.useEffect(() => {
    // Create a media query list for the mobile breakpoint
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    // Handler called whenever the viewport crosses the breakpoint threshold
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }
    // Listen for future changes (e.g. window resize, device rotation)
    mql.addEventListener("change", onChange)
    // Set the initial value synchronously on mount
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    // Clean up the event listener on unmount
    return () => mql.removeEventListener("change", onChange)
  }, [])

  // Coerce undefined → false for a stable boolean return type
  return !!isMobile
}
