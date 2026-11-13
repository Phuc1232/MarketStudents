import { useEffect, useRef, useState } from 'react'
import { api, errText } from '../../lib/api'

type Result = {
  file_id: string; thumbnail_url: string; detail_url: string
  status: 'processing' | 'ready' | 'error'; message?: string; error_code?: number
}
type Item = {
  id: string; file: File; preview: string; file_id?: string
  thumbnail_url?: string; detail_url?: string
  status: 'uploading' | 'processing' | 'ready' | 'error'
  deadline: number; message?: string; retryUpload: boolean
}

export function useProductUploads() {
  const [images, setImages] = useState<Item[]>([])
  const current = useRef<Item[]>([])
  const alive = useRef(true)
  const queue = useRef<string[]>([])
  const active = useRef(0)
  const sequence = useRef(0)
  const requests = useRef(new Set<AbortController>())

  function update(fn: (items: Item[]) => Item[]) {
    if (!alive.current) return
    current.current = fn(current.current)
    setImages(current.current)
  }
  async function bounded<T>(fn: (signal: AbortSignal) => Promise<T>): Promise<T> {
    const controller = new AbortController()
    requests.current.add(controller)
    const timer = window.setTimeout(() => controller.abort(), 30000)
    try { return await fn(controller.signal) }
    finally { clearTimeout(timer); requests.current.delete(controller) }
  }
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      queue.current = []
      requests.current.forEach((request) => request.abort())
      current.current.forEach((item) => URL.revokeObjectURL(item.preview))
    }
  }, [])

  function pump() {
    while (alive.current && active.current < 2 && queue.current.length) {
      const id = queue.current.shift()!
      const item = current.current.find((image) => image.id === id)
      if (!item) continue
      active.current++
      const body = new FormData()
      body.append('files', item.file)
      void bounded((signal) => api.upload<{ images: Result[] }>('/upload/images', body, signal))
        .then(({ images: results }) => {
          const result = results[0]
          if (!result?.file_id || !result.thumbnail_url || !result.detail_url) {
            throw new Error('API upload chưa trả đủ dữ liệu ảnh. Kiểm tra phiên bản backend.')
          }
          update((items) => items.map((image) => image.id === id ? {
            ...image, ...result, deadline: Date.now() + 30000, retryUpload: false,
          } : image))
        })
        .catch((error) => update((items) => items.map((image) => image.id === id ? {
          ...image, status: 'error', message: errText(error), retryUpload: true,
        } : image)))
        .finally(() => { active.current--; pump() })
    }
  }

  useEffect(() => {
    if (!images.some((image) => image.status === 'processing')) return
    let cancelled = false
    const timer = window.setTimeout(async () => {
      const pending = current.current.filter((image) => image.status === 'processing')
      const expired = new Set(pending.filter((image) => Date.now() >= image.deadline).map((image) => image.id))
      if (expired.size) update((items) => items.map((image) => expired.has(image.id) ? {
        ...image, status: 'error', message: 'Ảnh chưa xử lý xong. Bấm thử lại để kiểm tra tiếp.',
      } : image))
      const valid = pending.filter((image) => !expired.has(image.id))
      if (!valid.length) return
      try {
        const response = await bounded((signal) => api.post<{ images: Result[] }>(
          '/upload/images/status', { file_ids: valid.map((image) => image.file_id) }, undefined, signal,
        ))
        if (cancelled) return
        update((items) => items.map((item) => {
          const result = response.images.find((image) => image.file_id === item.file_id)
          if (!result || item.status !== 'processing') return item
          return { ...item, ...result, retryUpload: result.error_code === 410 || result.error_code === 403 }
        }))
      } catch (error) {
        if (!cancelled) update((items) => items.map((item) => valid.some((image) => image.id === item.id) ? {
          ...item, status: 'error', message: errText(error),
        } : item))
      }
    }, 2000)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [images])

  function add(files: File[]) {
    const selected = files.slice(0, 5 - current.current.length)
    const newItems: Item[] = selected.map((file) => {
      const valid = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type) && file.size <= 10 * 1024 * 1024
      return {
        id: `${Date.now()}-${++sequence.current}`, file, preview: URL.createObjectURL(file), deadline: 0,
        status: valid ? 'uploading' : 'error', retryUpload: true,
        message: valid ? undefined : 'Chọn JPG, PNG hoặc WebP không quá 10MB.',
      }
    })
    update((items) => [...items, ...newItems])
    queue.current.push(...newItems.filter((item) => item.status === 'uploading').map((item) => item.id))
    pump()
  }
  function remove(id: string) {
    const item = current.current.find((image) => image.id === id)
    if (item) URL.revokeObjectURL(item.preview)
    update((items) => items.filter((image) => image.id !== id))
    queue.current = queue.current.filter((queued) => queued !== id)
  }
  function retry(id: string) {
    const item = current.current.find((image) => image.id === id)
    if (!item || item.status !== 'error') return
    if (item.retryUpload && (!['image/jpeg', 'image/png', 'image/webp'].includes(item.file.type) || item.file.size > 10 * 1024 * 1024)) return
    update((items) => items.map((image) => image.id === id ? {
      ...image, status: image.retryUpload ? 'uploading' : 'processing',
      deadline: Date.now() + 30000, message: undefined,
    } : image))
    if (item.retryUpload) { queue.current.push(id); pump() }
  }
  return { images, add, remove, retry, ready: images.length > 0 && images.every((image) => image.status === 'ready') }
}
