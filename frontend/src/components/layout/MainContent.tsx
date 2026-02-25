import { AnimatePresence, motion } from 'framer-motion'
import type { ReactNode } from 'react'

interface MainContentProps {
  viewKey: string
  children: ReactNode
}

export function MainContent({ viewKey, children }: MainContentProps) {
  return (
    <main className="flex-1 flex flex-col">
      <AnimatePresence mode="wait">
        <motion.section
          key={viewKey}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          className="flex-1 flex flex-col"
        >
          {children}
        </motion.section>
      </AnimatePresence>
    </main>
  )
}
