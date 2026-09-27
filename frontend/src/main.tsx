import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth'
import { DialogProvider, ToastProvider } from './components/ui'
import { applyTheme, storedTheme } from './theme'
import './index.css'

applyTheme(storedTheme())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <DialogProvider>
            <App />
          </DialogProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
