import { useState } from 'react'
import { Outlet, NavLink, useMatch, useNavigate } from 'react-router-dom'
import {
  Menu, X, Home, BookOpen, Feather, MessageSquareQuote, Mic, Fingerprint, LogOut,
  type LucideIcon,
} from 'lucide-react'
import QuillLogo from '@/components/ui/QuillLogo'
import { useAuthStore, usePack } from '@/stores/authStore'

interface NavItem { to: string; label: string; icon: LucideIcon }

export default function AppLayout() {
  const { user, logout } = useAuthStore()
  const pack = usePack()
  const navGroups: { label: string; items: NavItem[] }[] = [
    {
      label: 'Write',
      items: [
        { to: '/dashboard', label: 'Desk', icon: Home },
        { to: '/projects', label: 'Manuscripts', icon: BookOpen },
      ],
    },
    {
      label: 'Your material',
      items: [
        { to: '/voice-profile', label: 'Voice', icon: Feather },
        { to: '/testimonies', label: pack.nav.stories, icon: MessageSquareQuote },
        { to: '/sermons', label: pack.nav.sources, icon: Mic },
        { to: '/ministry-dna', label: pack.nav.dna, icon: Fingerprint },
      ],
    },
  ]
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  // The chapter editor needs the width, so the sidebar shrinks to an icon rail there.
  const inEditor = useMatch('/projects/:id/chapters/:chapterId') !== null

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2.5 px-3 py-2.5 rounded text-sm transition-colors ${
      isActive
        ? 'bg-study-600 text-paper-100'
        : 'text-study-200 hover:text-paper-100 hover:bg-study-600/60'
    }`

  const NavContent = () => (
    <>
      <nav className="flex-1 px-3 py-2">
        {navGroups.map((group) => (
          <div key={group.label}>
            <p className="folio text-study-200 px-3 pt-4 pb-1.5">{group.label}</p>
            <div className="space-y-0.5">
              {group.items.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} onClick={() => setMobileOpen(false)} className={navLinkClass}>
                  <Icon size={16} aria-hidden="true" /> {label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-study-600 text-sm">
        <p className="text-paper-100 truncate px-3">{user?.full_name}</p>
        <p className="text-study-200 truncate px-3 text-xs mb-2">{user?.email}</p>
        <button
          onClick={handleLogout}
          className="w-full text-left px-3 py-1.5 rounded text-study-200 hover:text-paper-100 hover:bg-study-600/60 transition-colors text-sm"
        >
          Log out
        </button>
      </div>
    </>
  )

  const RailContent = () => (
    <>
      <nav className="flex-1 flex flex-col items-center gap-1 py-3" aria-label="Main">
        {navGroups.flatMap((g) => g.items).map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            aria-label={label}
            title={label}
            className={({ isActive }) =>
              `flex items-center justify-center w-11 h-11 rounded transition-colors ${
                isActive ? 'bg-study-600 text-paper-100' : 'text-study-200 hover:text-paper-100 hover:bg-study-600/60'
              }`
            }
          >
            <Icon size={18} />
          </NavLink>
        ))}
      </nav>
      <div className="py-3 border-t border-study-600 flex justify-center">
        <button
          onClick={handleLogout}
          aria-label="Log out"
          title="Log out"
          className="flex items-center justify-center w-11 h-11 rounded text-study-200 hover:text-paper-100 hover:bg-study-600/60 transition-colors"
        >
          <LogOut size={18} />
        </button>
      </div>
    </>
  )

  return (
    <div className="min-h-screen bg-paper flex">
      {/* Desktop sidebar — hidden on mobile; an icon rail inside the editor */}
      {inEditor ? (
        <aside className="hidden md:flex w-16 bg-study-700 text-study-50 flex-col flex-shrink-0">
          <div className="h-[61px] flex items-center justify-center border-b border-study-600 text-paper-100" title="The Scribe">
            <Feather size={20} className="text-seal-200" aria-label="The Scribe" />
          </div>
          <RailContent />
        </aside>
      ) : (
        <aside className="hidden md:flex w-56 bg-study-700 text-study-50 flex-col flex-shrink-0">
          <div className="px-6 py-5 border-b border-study-600">
            <span className="text-study-50"><QuillLogo size="sm" /></span>
          </div>
          <NavContent />
        </aside>
      )}

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
          <button onClick={() => setMobileOpen(false)} className="text-study-200 hover:text-paper-100" aria-label="Close menu">
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
            aria-label="Open menu"
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
