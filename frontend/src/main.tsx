import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app/App'
import './styles/global.css'
import './styles/header.css'
import './styles/footer.css'
import './features/auth/auth.css'
import './features/products/products.css'
import './features/chat/messages.css'
import './features/users/profile.css'
import './styles/mobile.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
