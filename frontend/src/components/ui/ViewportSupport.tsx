import { useEffect } from 'react'

/** Track the visible area on browsers where the keyboard overlays the layout viewport. */
export default function ViewportSupport() {
  useEffect(() => {
    const viewport = window.visualViewport
    const root = document.documentElement
    const update = () => {
      if (viewport && viewport.scale !== 1) return // Preserve pinch zoom.
      root.style.setProperty('--visual-height', `${viewport?.height ?? window.innerHeight}px`)
      root.style.setProperty('--visual-top', `${viewport?.offsetTop ?? 0}px`)
      root.dataset.keyboard = String(!!viewport && window.innerHeight - viewport.height > 120)
    }
    update()
    viewport?.addEventListener('resize', update)
    viewport?.addEventListener('scroll', update)
    window.addEventListener('resize', update)
    return () => {
      viewport?.removeEventListener('resize', update)
      viewport?.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
      root.style.removeProperty('--visual-height'); root.style.removeProperty('--visual-top'); delete root.dataset.keyboard
    }
  }, [])
  return null
}
