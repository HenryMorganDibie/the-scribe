import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useAuthStore } from '@/stores/authStore'

import Landing from '@/pages/Landing'
import Login from '@/pages/auth/Login'
import Signup from '@/pages/auth/Signup'
import Onboarding from '@/pages/Onboarding'
import Dashboard from '@/pages/Dashboard'
import VoiceProfile from '@/pages/VoiceProfile'
import Projects from '@/pages/Projects'
import ManuscriptStudio from '@/pages/ManuscriptStudio'
import ChapterEditor from '@/pages/ChapterEditor'
import Testimonies from '@/pages/Testimonies'
import Sermons from '@/pages/Sermons'
import MinistryDNA from '@/pages/MinistryDNA'
import AppLayout from '@/components/layout/AppLayout'

function ProtectedRoute({ children, requireOnboarded = true }: { children: JSX.Element; requireOnboarded?: boolean }) {
  const { user, loading } = useAuthStore()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper">
        <div className="animate-pulse text-seal font-display text-2xl">The Scribe</div>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />
  if (requireOnboarded && !user.onboarded) return <Navigate to="/onboarding" replace />
  if (!requireOnboarded && user.onboarded) return <Navigate to="/dashboard" replace />

  return children
}

export default function App() {
  const { fetchMe } = useAuthStore()

  useEffect(() => {
    fetchMe()
  }, [fetchMe])

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: { background: '#1E1E1E', color: '#F5F0E8', border: '1px solid #3A3530' },
        }}
      />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        <Route
          path="/onboarding"
          element={
            <ProtectedRoute requireOnboarded={false}>
              <Onboarding />
            </ProtectedRoute>
          }
        />

        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/voice-profile" element={<VoiceProfile />} />
          <Route path="/testimonies" element={<Testimonies />} />
          <Route path="/sermons" element={<Sermons />} />
          <Route path="/ministry-dna" element={<MinistryDNA />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<ManuscriptStudio />} />
          <Route path="/projects/:id/chapters/:chapterId" element={<ChapterEditor />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
