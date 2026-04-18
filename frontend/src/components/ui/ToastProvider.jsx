import React, { createContext, useContext, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '../../lib/utils'
import { X } from 'lucide-react'

const ToastContext = createContext(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

let toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const showToast = useCallback((message, type = 'info') => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5000)
  }, [])

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const typeStyles = {
    success: 'bg-skill-green/15 border-skill-green/30 text-on-surface',
    info: 'bg-surface-lowest border-outline-variant text-on-surface',
    warning: 'bg-skill-orange/15 border-skill-orange/30 text-on-surface',
  }

  const dotStyles = {
    success: 'bg-skill-green',
    info: 'bg-primary',
    warning: 'bg-skill-orange',
  }

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 pointer-events-none">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 80, scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              className={cn(
                'pointer-events-auto flex items-center gap-3 px-5 py-3.5 rounded-lg border shadow-lg max-w-sm',
                typeStyles[toast.type]
              )}
            >
              <span className={cn('w-2 h-2 rounded-full flex-shrink-0', dotStyles[toast.type])} />
              <span className="text-[13px] font-medium flex-1">{toast.message}</span>
              <button
                onClick={() => dismiss(toast.id)}
                className="text-on-surface-variant hover:text-on-surface transition-colors flex-shrink-0"
              >
                <X size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
