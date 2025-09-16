import React, { useState } from 'react'
import { SendIcon } from 'lucide-react'

const ChatInput = ({ onSendMessage }: { onSendMessage: (msg: string) => void }) => {
  const [message, setMessage] = useState('')
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (message.trim()) {
      onSendMessage(message)
      setMessage('')
    }
  }
  return (
    <form onSubmit={handleSubmit} className="relative">
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Ask about SF Board of Supervisors meetings..."
        className="w-full p-5 pr-14 rounded-lg border-2 border-blue-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-lg shadow-md"
      />
      <button
        type="submit"
        className="absolute right-3 top-1/2 transform -translate-y-1/2 bg-blue-600 text-white p-3 rounded-full hover:bg-blue-700 transition-colors shadow-sm"
        disabled={!message.trim()}
      >
        <SendIcon className="h-6 w-6" />
      </button>
    </form>
  )
}
export default ChatInput
