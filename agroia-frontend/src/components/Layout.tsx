import React, { useState } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import { Menu, X } from 'lucide-react'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const location = useLocation()

  return (
    <div className="flex h-screen bg-white">
      {/* Mobile Menu Button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="fixed top-4 right-4 z-50 lg:hidden p-2 hover:bg-gray-100 rounded-lg"
      >
        {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Sidebar */}
      {(sidebarOpen || window.innerWidth >= 1024) && (
        <div className="fixed lg:relative w-80 h-full bg-gradient-to-b from-white to-gray-50 border-r border-gray-200 overflow-y-auto z-40">
          <Sidebar />
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <nav className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4 z-30">
          <div className="flex-1" />
          <div className="text-sm text-gray-500">
            {location.pathname === '/' && 'Chat'}
            {location.pathname === '/dashboard' && 'Dashboard'}
            {location.pathname === '/consultas' && 'Consultas'}
          </div>
        </nav>
        <main className="p-6 max-w-7xl mx-auto w-full">
          {children}
        </main>
      </div>
    </div>
  )
}
