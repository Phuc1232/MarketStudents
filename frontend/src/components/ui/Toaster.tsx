import { useEffect, useState } from 'react'

interface T { id: number; message: string; kind: 'ok' | 'err' }

export default function Toaster() {
  const [items, setItems] = useState<T[]>([])
  useEffect(() => {
    let n = 0
    const h = (e: Event) => {
      const { message, kind } = (e as CustomEvent).detail
      const id = ++n
      setItems((x) => [...x, { id, message, kind }])
      setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 3600)
    }
    window.addEventListener('cm:toast', h)
    return () => window.removeEventListener('cm:toast', h)
  }, [])
  return (
    <div className="toaster" role="status" aria-live="polite">
      {items.map((i) => (
        <div key={i.id} className={`toast toast-${i.kind}`}>{i.message}</div>
      ))}
    </div>
  )
}
