import { useEffect, useRef, useCallback, useState } from 'react'
import { WsEvent } from '../types'

type MessageHandler = (event: WsEvent) => void

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`

export function useWebSocket(onMessage: MessageHandler) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [reconnectCount, setReconnectCount] = useState(0)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setReconnectCount(0)
      // Start heartbeat
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 30000)
      ws.addEventListener('close', () => clearInterval(ping))
    }

    ws.onmessage = (e) => {
      if (e.data === 'pong') return
      try {
        const parsed = JSON.parse(e.data) as WsEvent
        onMessageRef.current(parsed)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      // Exponential backoff reconnect
      setReconnectCount(c => {
        const delay = Math.min(1000 * 2 ** c, 30000)
        setTimeout(connect, delay)
        return c + 1
      })
    }

    ws.onerror = () => ws.close()
  }, [])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  return { connected, reconnectCount }
}
