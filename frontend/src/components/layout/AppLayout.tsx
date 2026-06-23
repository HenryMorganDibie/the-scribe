import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import QuillLogo from '@/components/ui/QuillLogo'
import { useAuthStore } from '@/stores/authStore'

const navItems = [
  { to: '/dashboard', label: 'Desk' },
  { to: '/projects', label: 'Manuscripts' },
  { to: '/voice-profile', label: 'Voice' },
  { to: '/testimonies', label: 'Testimonies' },
  { to: '/sermons', label: 'Sermons' },
  { to: '/ministry-dna', label: 'Ministry DNA' },
]

export default function AppLayout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const NavContent = () => (
    <>
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `block px-3 py-2.5 rounded text-sm transition-colors ${
                isActive
                  ? 'bg-study-600 text-paper-100'
                  : 'text-study-200 hover:text-paper-100 hover:bg-study-600/60'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-study-600 text-sm">
        <p className="text-paper-100 truncate px-3">{user?.full_name}</p>
        <p className="text-study-300 truncate px-3 text-xs mb-2">{user?.email}</p>
        <button
          onClick={handleLogout}
          className="w-full text-left px-3 py-1.5 rounded text-study-300 hover:text-paper-100 hover:bg-study-600/60 transition-colors text-sm"
        >
          Log out
        </button>
      </div>
    </>
  )

  return (
    <div className="min-h-screen bg-paper flex">
      {/* Desktop sidebar — hidden on mobile */}
      <aside className="hidden md:flex w-56 bg-study-700 text-study-50 flex-col flex-shrink-0">
        <div className="px-6 py-5 border-b border-study-600">
          <span className="text-study-50"><QuillLogo size="sm" /></span>
        </div>
        <NavContent />
      </aside>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-study-700 text-study-50 flex flex-col transform transition-transform duration-200 md:hidden ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="px-6 py-5 border-b border-study-600 flex items-center justify-between">
          <span className="text-study-50"><QuillLogo size="sm" /></span>
          <button onClick={() => setMobileOpen(false)} className="text-study-300 hover:text-paper-100">
            <X size={20} />
          </button>
        </div>
        <NavContent />
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <div className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-paper-300 bg-paper sticky top-0 z-30">
          <button
            onClick={() => setMobileOpen(true)}
            className="text-study-400 hover:text-study-700 p-1"
          >
            <Menu size={22} />
          </button>
          <span className="text-study-50">
            <QuillLogo size="sm" />
          </span>
        </div>

        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
