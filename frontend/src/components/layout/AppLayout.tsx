import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import QuillLogo from '@/components/ui/QuillLogo'
import { useAuthStore } from '@/stores/authStore'

const navItems = [
  { to: '/dashboard', label: 'Desk' },
  { to: '/projects', label: 'Manuscripts' },
  { to: '/voice-profile', label: 'Voice' },
  { to: '/testimonies', label: 'Testimonies' },
]

export default function AppLayout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-paper flex">
      {/* Sidebar — study chrome, warm charcoal */}
      <aside className="w-56 bg-study-700 text-study-50 flex flex-col flex-shrink-0">
        <div className="px-6 py-5 border-b border-study-600">
          <span className="text-study-50">
            <QuillLogo size="sm" />
          </span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {navItems.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `block px-3 py-2 rounded text-sm transition-colors ${
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
      </aside>

      {/* Main content — manuscript page */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
