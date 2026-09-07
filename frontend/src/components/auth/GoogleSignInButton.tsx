import { useEffect, useRef } from 'react'

type GoogleCredentialResponse = {
  credential?: string
}

type GoogleIdentityApi = {
  initialize: (config: {
    client_id: string
    callback: (response: GoogleCredentialResponse) => void
    auto_select: boolean
  }) => void
  renderButton: (
    parent: HTMLElement,
    options: { theme: string; size: string; text: string; width: number }
  ) => void
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdentityApi } }
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID
const GOOGLE_SCRIPT_ID = 'google-identity-services'

interface GoogleSignInButtonProps {
  onCredential: (credential: string) => Promise<void>
  onError: (message: string) => void
}

export default function GoogleSignInButton({ onCredential, onError }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const onCredentialRef = useRef(onCredential)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onCredentialRef.current = onCredential
    onErrorRef.current = onError
  }, [onCredential, onError])

  useEffect(() => {
    const container = containerRef.current
    if (!GOOGLE_CLIENT_ID || !container) return

    const renderButton = () => {
      if (!window.google || !containerRef.current) return

      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        auto_select: false,
        callback: (response) => {
          if (!response.credential) {
            onErrorRef.current('Google did not return a sign-in credential')
            return
          }
          void onCredentialRef.current(response.credential)
        },
      })
      containerRef.current.replaceChildren()
      window.google.accounts.id.renderButton(containerRef.current, {
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        width: 320,
      })
    }

    const existingScript = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null
    if (window.google) {
      renderButton()
    } else if (existingScript) {
      existingScript.addEventListener('load', renderButton, { once: true })
    } else {
      const script = document.createElement('script')
      script.id = GOOGLE_SCRIPT_ID
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.onload = renderButton
      script.onerror = () => onErrorRef.current('Unable to load Google sign-in')
      document.head.appendChild(script)
    }
  }, [])

  if (!GOOGLE_CLIENT_ID) return null

  return <div ref={containerRef} className="flex justify-center" />
}
