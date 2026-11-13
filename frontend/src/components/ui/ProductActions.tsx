import { ReactNode, useEffect, useRef } from 'react'

export default function ProductActions({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDetailsElement>(null)
  useEffect(() => {
    const query = matchMedia('(max-width: 680px)')
    const update = () => { if (ref.current) ref.current.open = !query.matches }
    update(); query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return <details className="product-actions-menu" ref={ref} open><summary>Thao tác với tin</summary><div className="mp-actions">{children}</div></details>
}
