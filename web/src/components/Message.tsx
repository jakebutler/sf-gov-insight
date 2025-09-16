import React from 'react'
import { UserIcon } from 'lucide-react'

const Message = ({ message }: { message: { text: string; isUser: boolean; id: number } }) => {
  const { text, isUser, id } = message
  const isWelcomeMessage = id === 1 && !isUser
  const welcomeText = isWelcomeMessage ? text.split('!')[0] + '!' : null
  const remainingText = isWelcomeMessage ? text.substring((welcomeText || '').length) : null
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`flex max-w-[80%] ${
          isUser
            ? 'bg-blue-600 text-white rounded-tl-lg rounded-tr-lg rounded-bl-lg'
            : 'bg-gray-100 text-gray-800 rounded-tl-lg rounded-tr-lg rounded-br-lg'
        } p-4 shadow-sm`}
      >
        <div className="flex items-start">
          {!isUser && (
            <div className="flex-shrink-0 mr-3">
              <div className="h-10 w-10 rounded-full bg-blue-700 flex items-center justify-center text-white">
                <div className="h-6 w-6" />
              </div>
            </div>
          )}
          <div className="flex-1">
            {isWelcomeMessage ? (
              <p className="text-base">
                <span className="font-bold">{welcomeText}</span>
                {remainingText}
              </p>
            ) : (
              <p className="text-base whitespace-pre-wrap">{text}</p>
            )}
          </div>
          {isUser && (
            <div className="flex-shrink-0 ml-3">
              <div className="h-10 w-10 rounded-full bg-blue-500 flex items-center justify-center text-white">
                <UserIcon className="h-6 w-6" />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
export default Message
