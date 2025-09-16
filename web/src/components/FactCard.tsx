import React, { useEffect, useState } from 'react'
import { LightbulbIcon } from 'lucide-react'
import { motion } from 'framer-motion'

const facts = [
  'Housing affordability was mentioned in every Board meeting in the last 6 months, but no related items were passed.',
  'Supervisor Chan spoke the most during public comment periods, averaging 15 minutes per meeting.',
  'The Board discussed climate initiatives in 78% of meetings, but only allocated 3% of the budget to related projects.',
  'The most attended meeting this year was about the homeless shelter proposal, with 342 public attendees.',
  "Public transportation funding has decreased by 12% compared to last year's budget allocation.",
  'The Board has passed 24 resolutions this year, but only 9 ordinances.',
  'District 6 residents submitted the most public comments, accounting for 31% of all feedback.',
  'The average Board meeting lasted 4.2 hours, with the longest being 7.5 hours in March.',
]

const FactCard = ({ isHero = false }: { isHero?: boolean }) => {
  const [currentFact, setCurrentFact] = useState(0)
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentFact((prev) => (prev + 1) % facts.length)
    }, 10000)
    return () => clearInterval(interval)
  }, [])
  return (
    <motion.div
      className={`${
        isHero
          ? 'bg-gradient-to-r from-blue-700 to-blue-600 text-white border-blue-500'
          : 'bg-yellow-50 border-yellow-200 text-gray-700'
      } border rounded-lg shadow-md overflow-hidden`}
      layout
      transition={{
        layout: { duration: 0.5, ease: 'easeInOut' },
      }}
    >
      <div className={isHero ? 'p-8' : 'p-4'}>
        <div className={`flex items-center ${isHero ? 'mb-4 justify-center' : 'mb-2'}`}>
          <LightbulbIcon className={`${isHero ? 'h-8 w-8' : 'h-5 w-5'} mr-2 ${isHero ? 'text-yellow-300' : 'text-yellow-700'}`} />
          <h3 className={`font-bold ${isHero ? 'text-2xl' : 'text-lg'}`}>Did you know?</h3>
        </div>
        <div className={`${isHero ? 'py-0' : 'py-0'}`}>
          <p className={`${isHero ? 'text-xl text-blue-50 text-center max-w-3xl mx-auto' : 'text-gray-700'}`}>
            {facts[currentFact]}
          </p>
        </div>
        <div className={`${isHero ? 'mt-4' : 'mt-2'} flex justify-between items-center ${isHero ? 'max-w-xl mx-auto' : ''}`}>
          <span className={`text-xs ${isHero ? 'text-blue-200' : 'text-gray-500'}`}>
            Fact {currentFact + 1} of {facts.length}
          </span>
          <div className="flex space-x-1">
            {facts.map((_, index) => (
              <span
                key={index}
                className={`block rounded-full ${
                  isHero
                    ? index === currentFact
                      ? 'h-2 w-2 bg-yellow-300'
                      : 'h-2 w-2 bg-blue-400'
                    : index === currentFact
                      ? 'h-1.5 w-1.5 bg-yellow-500'
                      : 'h-1.5 w-1.5 bg-yellow-200'
                }`}
              ></span>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  )
}
export default FactCard
