import { useEffect, useRef, useState } from 'react'
import { GOOGLE_CLIENT_ID } from '../../lib/api'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: { credential: string; select_by?: string }) => void
            auto_select?: boolean
            cancel_on_tap_outside?: boolean
          }) => void
          renderButton: (
            parent: HTMLElement,
            options: {
              type?: 'standard' | 'icon'
              theme?: 'outline' | 'filled_blue' | 'filled_black'
              size?: 'large' | 'medium' | 'small'
              text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
              shape?: 'rectangular' | 'pill' | 'circle' | 'square'
              logo_alignment?: 'left' | 'center'
              width?: number | string
              locale?: string
            },
          ) => void
          prompt: (momentListener?: (notification: any) => void) => void
          cancel: () => void
        }
      }
    }
  }
}

export function GoogleLogo({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
      <path
        fill="#4285F4"
        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.99 0 12s.45 3.82 1.25 5.42l4.03-3.15z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
      />
    </svg>
  )
}

interface GoogleLoginButtonProps {
  onSuccess: (idToken: string) => void
  onError?: (error: string) => void
  text?: 'signin_with' | 'signup_with' | 'continue_with'
  disabled?: boolean
}

export default function GoogleLoginButton({
  onSuccess,
  onError,
  text = 'continue_with',
  disabled = false,
}: GoogleLoginButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [scriptLoaded, setScriptLoaded] = useState(false)
  const [btnRendered, setBtnRendered] = useState(false)

  // 1. Tải Google Identity Services (GSI) script nếu chưa có
  useEffect(() => {
    if (window.google?.accounts?.id) {
      setScriptLoaded(true)
      return
    }

    const scriptId = 'google-gsi-client'
    let script = document.getElementById(scriptId) as HTMLScriptElement | null
    if (!script) {
      script = document.createElement('script')
      script.id = scriptId
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.defer = true
      document.head.appendChild(script)
    }

    const onLoad = () => setScriptLoaded(true)
    const onErr = () => onError?.('Không thể tải Google Sign-In SDK.')

    script.addEventListener('load', onLoad)
    script.addEventListener('error', onErr)

    return () => {
      script?.removeEventListener('load', onLoad)
      script?.removeEventListener('error', onErr)
    }
  }, [onError])

  // 2. Khởi tạo và render nút Google chính thức
  useEffect(() => {
    if (!scriptLoaded || !containerRef.current || !window.google?.accounts?.id) return

    try {
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (res) => {
          if (res?.credential) {
            onSuccess(res.credential)
          } else {
            onError?.('Đăng nhập Google thất bại (không nhận được mã xác thực).')
          }
        },
        auto_select: false,
        cancel_on_tap_outside: true,
      })

      // Chiều rộng nút: tối đa 400px, tối thiểu 200px
      const measured = containerRef.current.clientWidth || 376
      const buttonWidth = Math.max(200, Math.min(measured, 400))

      containerRef.current.innerHTML = ''
      window.google.accounts.id.renderButton(containerRef.current, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text,
        shape: 'rectangular',
        logo_alignment: 'left',
        width: buttonWidth,
        locale: 'vi',
      })

      setBtnRendered(true)
    } catch (e) {
      console.warn('Lỗi render nút Google:', e)
    }
  }, [scriptLoaded, text, onSuccess, onError])

  const labelText =
    text === 'signup_with'
      ? 'Đăng ký với Google'
      : text === 'signin_with'
        ? 'Đăng nhập với Google'
        : 'Tiếp tục với Google'

  return (
    <div className="google-auth-section">
      <div
        ref={containerRef}
        className="google-btn-container"
        style={{
          display: btnRendered && !disabled ? 'flex' : 'none',
          pointerEvents: disabled ? 'none' : 'auto',
          opacity: disabled ? 0.6 : 1,
        }}
      />
      {(!btnRendered || disabled) && (
        <button
          type="button"
          className="google-fallback-btn"
          disabled={disabled || !scriptLoaded}
          onClick={() => {
            if (window.google?.accounts?.id) {
              window.google.accounts.id.prompt()
            }
          }}
          title={labelText}
        >
          <GoogleLogo size={18} />
          <span>{disabled ? 'Đang xử lý...' : labelText}</span>
        </button>
      )}
    </div>
  )
}
