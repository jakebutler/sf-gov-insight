import React, { useEffect, useRef } from 'react'
import Message from './Message'

const ChatInterface = ({ messages }: { messages: any[] }) => {
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
  useEffect(() => {
    scrollToBottom()
  }, [messages])
  return (
    <div className="flex-1 overflow-y-auto rounded-lg bg-white shadow-md p-5 mb-5 min-h-[400px]">
      <div className="space-y-5">
        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}
        <div ref={messagesEndRef} />
      </div>
    </div>
  )
}
export default ChatInterface
