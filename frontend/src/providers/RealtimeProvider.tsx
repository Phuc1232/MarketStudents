import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api, getToken, toast, useAuth, wsUrl } from '../lib/api'

export interface IncomingMessage {
  message_id: number
  conversation_id: number
  sender_id: number
  content: string
  sent_at: string
  sender?: { user_id: number; full_name: string; avatar_url?: string | null }
  product?: { title: string }
}
export interface MessageAlert { message: IncomingMessage; count: number }
interface RealtimeState {
  notificationUnread: number
  messageUnread: number
  connected: boolean
  alerts: MessageAlert[]
  dismiss: (conversationId: number) => void
  refresh: () => Promise<void>
}
const Context = createContext<RealtimeState | null>(null)
const dispatch = (name: string, detail?: unknown) => window.dispatchEvent(new CustomEvent(name, { detail }))

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { token, userId } = useAuth()
  const [notificationUnread, setNotificationUnread] = useState(0)
  const [messageUnread, setMessageUnread] = useState(0)
  const [connected, setConnected] = useState(false)
  const [alerts, setAlerts] = useState<MessageAlert[]>([])
  const generation = useRef(0)
  const channel = useRef<BroadcastChannel | null>(null)
  const sequence = useRef(0)

  const refreshCounts = useCallback(async () => {
    if (!token || token !== getToken()) return
    const version = generation.current
    const request = ++sequence.current
    const results = await Promise.allSettled([
      api.get<{ unread_count: number }>('/interaction/notifications/unread-count'),
      api.get<{ unread_count: number }>('/interaction/messages/unread-count'),
    ])
    if (version !== generation.current || token !== getToken() || request !== sequence.current) return
    if (results[0].status === 'fulfilled') setNotificationUnread(results[0].value.unread_count)
    if (results[1].status === 'fulfilled') setMessageUnread(results[1].value.unread_count)
  }, [token])
  const refresh = useCallback(async () => {
    await refreshCounts()
    channel.current?.postMessage({ type: 'invalidate' })
  }, [refreshCounts])
  const dismiss = useCallback((id: number) => setAlerts((items) => items.filter((item) => item.message.conversation_id !== id)), [])

  useEffect(() => {
    generation.current++
    setNotificationUnread(0); setMessageUnread(0); setAlerts([]); setConnected(false)
    if (!token) return
    let dead = false
    let socket: WebSocket | null = null
    let heartbeat: number | undefined
    let retry: number | undefined
    let attempts = 0
    const seen = new Set<number>()
    const seenNotifications = new Set<number>()
    let lastPong = Date.now()
    const sync = () => {
      if (dead) return
      void refreshCounts()
      dispatch('cm:realtime-sync')
      dispatch('cm:notification')
    }
    if (typeof BroadcastChannel !== 'undefined') {
      const bc = new BroadcastChannel(`cm:realtime:${userId}`)
      channel.current = bc
      bc.onmessage = sync
    }
    const connect = () => {
      if (dead || getToken() !== token) return
      const ws = new WebSocket(wsUrl('/interaction/ws/notifications'))
      socket = ws
      ws.onopen = () => {
        if (dead || socket !== ws) { ws.close(); return }
        attempts = 0; lastPong = Date.now(); setConnected(true); sync()
        heartbeat = window.setInterval(() => {
          if (Date.now() - lastPong > 65000) { ws.close(); return }
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ action: 'ping' }))
        }, 25000)
      }
      ws.onmessage = (event) => {
        if (dead || socket !== ws || getToken() !== token) return
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'pong') { lastPong = Date.now(); return }
          if (payload.type === 'new_message') {
            const msg: IncomingMessage = payload.data
            if (!msg || !Number.isInteger(msg.message_id) || seen.has(msg.message_id)) return
            seen.add(msg.message_id)
            if (seen.size > 2000) seen.delete(seen.values().next().value!)
            dispatch('cm:chat-message', msg)
            void refreshCounts()
            const active = /^\/messages(?:\.html)?\/?$/.test(location.pathname)
              && Number(new URLSearchParams(location.search).get('c')) === msg.conversation_id
              && document.visibilityState === 'visible' && document.hasFocus()
            if (msg.sender_id !== userId && !active) {
              setAlerts((items) => {
                const previous = items.find((item) => item.message.conversation_id === msg.conversation_id)
                return [{ message: msg, count: (previous?.count ?? 0) + 1 }, ...items.filter((item) => item !== previous)].slice(0, 3)
              })
            }
          } else if (payload.type === 'read_receipt') {
            dispatch('cm:chat-read', payload.data)
            if (payload.data?.reader_id === userId && typeof payload.data.last_read_message_id === 'number') {
              setAlerts((items) => items.filter((item) => item.message.conversation_id !== payload.data.conversation_id
                || item.message.message_id > payload.data.last_read_message_id))
            }
            void refreshCounts()
          } else if (payload.type === 'new_notification') {
            const id = payload.data?.notification_id
            if (id && seenNotifications.has(id)) return
            if (id) {
              seenNotifications.add(id)
              if (seenNotifications.size > 2000) seenNotifications.delete(seenNotifications.values().next().value!)
            }
            toast(payload.data?.title ?? 'Bạn có thông báo mới')
            dispatch('cm:notification', payload.data)
            void refreshCounts()
          } else if (['notifications_updated', 'notification_read_ack', 'notification_read_all_ack'].includes(payload.type)) {
            dispatch('cm:notification')
            void refreshCounts()
          }
        } catch { /* Ignore malformed events; reconnect will reconcile persisted state. */ }
      }
      ws.onclose = (event) => {
        if (socket !== ws) return
        window.clearInterval(heartbeat)
        if (dead) return
        setConnected(false)
        if (![4401, 4403, 1008].includes(event.code)) {
          retry = window.setTimeout(connect, Math.min(30000, 1000 * 2 ** attempts++) + Math.random() * 500)
        }
      }
    }
    const onFocus = () => {
      if (document.visibilityState !== 'visible') return
      sync()
      if (!socket || socket.readyState === WebSocket.CLOSED) {
        window.clearTimeout(retry); connect()
      }
    }
    const onRead = () => { void refresh() }
    connect()
    void refreshCounts()
    // Reconcile counts even when an event was missed by a disconnected worker.
    const reconcile = window.setInterval(() => { if (document.visibilityState === 'visible') void refreshCounts() }, 30000)
    window.addEventListener('focus', onFocus)
    window.addEventListener('online', onFocus)
    document.addEventListener('visibilitychange', onFocus)
    window.addEventListener('cm:chat-count-refresh', onRead)
    return () => {
      dead = true; generation.current++
      window.clearInterval(heartbeat); window.clearInterval(reconcile); window.clearTimeout(retry)
      socket?.close(); channel.current?.close(); channel.current = null
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('online', onFocus)
      document.removeEventListener('visibilitychange', onFocus)
      window.removeEventListener('cm:chat-count-refresh', onRead)
    }
  }, [token, userId, refreshCounts, refresh, dismiss])

  return <Context.Provider value={{ notificationUnread, messageUnread, connected, alerts, dismiss, refresh }}>{children}</Context.Provider>
}

export function useRealtime() {
  const value = useContext(Context)
  if (!value) throw new Error('RealtimeProvider is required')
  return value
}
