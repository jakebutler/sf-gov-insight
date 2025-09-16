import React from 'react'

const Header = () => {
  return (
    <header className="bg-blue-700 text-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 py-4 flex items-center">
        <div className="h-8 w-8 mr-3" />
        <div>
          <h1 className="text-2xl font-bold">SF GovInsight</h1>
          <p className="text-sm text-blue-100">Making local government accessible</p>
        </div>
      </div>
    </header>
  )
}
export default Header
