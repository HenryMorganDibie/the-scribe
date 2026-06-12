import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Feather, BookOpen, ScrollText, LogOut, User } from 'lucide-react'
import QuillLogo from '@/components/ui/QuillLogo'
import { useAuthStore } from '@/stores/authStore'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/projects', label: 'Manuscripts', icon: BookOpen },
  { to: '/voice-profile', label: 'Voice DNA', icon: Feather },
  { to: '/testimonies', label: 'Testimony Vault', icon: ScrollText },
]

export default function AppLayout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-ink-950 flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-ink-700 flex flex-col bg-ink-900/60 backdrop-blur-sm">
        <div className="p-6 border-b border-ink-700">
          <QuillLogo size="sm" animate={false} />
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-gold-800/60 text-gold-400 shadow-gold-sm'
                    : 'text-ink-300 hover:text-ink-50 hover:bg-ink-800'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-ink-700">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg">
            <div className="w-8 h-8 rounded-full bg-gold-gradient flex items-center justify-center">
              <User size={16} className="text-ink-950" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-ink-50 truncate">{user?.full_name}</p>
              <p className="text-xs text-ink-400 truncate">{user?.email}</p>
            </div>
            <button onClick={handleLogout} className="text-ink-400 hover:text-gold-400 transition-colors" title="Log out">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
