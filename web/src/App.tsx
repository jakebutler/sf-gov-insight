import React, { useState } from 'react'
import Header from './components/Header'
import ChatInterface from './components/ChatInterface'
import FactCard from './components/FactCard'
import SourcesCard from './components/SourcesCard'
import ChatInput from './components/ChatInput'
import { motion, AnimatePresence } from 'framer-motion'

export function App() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Welcome to SF GovInsight! I can help you understand what's happening in San Francisco Board of Supervisors meetings. Ask me anything about recent meetings, specific topics, or board members.",
      isUser: false,
    },
  ])
  const [hasSubmittedQuestion, setHasSubmittedQuestion] = useState(false)
  const [loading, setLoading] = useState(false)
  const [latestSources, setLatestSources] = useState<any[]>([])

  const handleSendMessage = async (message: string) => {
    setHasSubmittedQuestion(true)
    const userMessage = {
      id: messages.length + 1,
      text: message,
      isUser: true,
    }
    setMessages((prev) => [...prev, userMessage])

    try {
      setLoading(true)
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: message, top_k: 5 }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Request failed')
      }
      const data = await res.json()
      const botResponse = {
        id: messages.length + 2,
        text: data.answer as string,
        isUser: false,
      }
      setMessages((prev) => [...prev, botResponse])
      setLatestSources(Array.isArray(data.sources) ? data.sources : [])
    } catch (e: any) {
      const botResponse = {
        id: messages.length + 2,
        text: `Sorry, I hit an error: ${e?.message || e}`,
        isUser: false,
      }
      setMessages((prev) => [...prev, botResponse])
      setLatestSources([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col w-full min-h-screen bg-gray-50">
      <Header />
      <div className="w-full max-w-7xl mx-auto px-4 py-6 flex-1 flex flex-col">
        <div className="max-w-4xl mx-auto w-full">
          <AnimatePresence>
            {!hasSubmittedQuestion ? (
              <>
                <motion.div
                  key="hero-fact"
                  initial={{ opacity: 1 }}
                  exit={{ opacity: 0, y: -20, transition: { duration: 0.3 } }}
                  className="w-full mb-6"
                >
                  <FactCard isHero={true} />
                </motion.div>
                <div className="flex flex-col flex-1">
                  <ChatInterface messages={messages} />
                  <ChatInput onSendMessage={handleSendMessage} />
                </div>
              </>
            ) : (
              <motion.div
                className="flex flex-col md:flex-row gap-6 flex-1"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3, delay: 0.2 }}
              >
                <motion.div
                  className="w-full md:w-3/4 flex flex-col"
                  initial={{ width: '100%' }}
                  animate={{ width: '75%' }}
                  transition={{ duration: 0.5, ease: 'easeInOut' }}
                >
                  <ChatInterface messages={messages} />
                  <ChatInput onSendMessage={handleSendMessage} />
                  {loading && (
                    <div className="text-sm text-gray-500 mt-2">Thinking…</div>
                  )}
                </motion.div>
                <motion.div
                  className="w-full md:w-1/4 mt-6 md:mt-0"
                  initial={{ x: -50, opacity: 0, width: '0%' }}
                  animate={{ x: 0, opacity: 1, width: '25%' }}
                  transition={{ duration: 0.5, ease: 'easeInOut', delay: 0.3 }}
                >
                  {/* Show sources from the latest response; fallback to FactCard if none yet */}
                  {latestSources && latestSources.length > 0 ? (
                    <SourcesCard sources={latestSources} />
                  ) : (
                    <FactCard isHero={false} />
                  )}
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
