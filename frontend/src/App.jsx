import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Auth from './components/Auth';
import Dashboard from './pages/Dashboard';
import Onboarding from './pages/Onboarding';
import ErrorBoundary from './components/ErrorBoundary';
import { authAPI, clearTokens } from './services/api';

function AuthPage() {
  return (
    <div className="bg-background iridescent-bg text-on-background font-body min-h-screen overflow-hidden selection:bg-primary selection:text-on-primary">
      <main className="flex min-h-screen w-full relative">
        {/* Background Video */}
        <div className="absolute inset-0 z-0 overflow-hidden">
          <video
            className="w-full h-full object-cover"
            autoPlay
            loop
            muted
            playsInline
            poster="/poster.jpg"
          >
            <source src="/video.mp4" type="video/mp4" />
          </video>
          <div className="absolute inset-0 bg-gradient-to-r from-transparent to-black/30 opacity-90" />
          <div className="absolute top-1/4 -left-20 w-80 h-80 bg-primary-dim/30 aurora-blur rounded-full" />
          <div className="absolute bottom-1/4 right-0 w-96 h-96 bg-secondary/20 aurora-blur rounded-full" />
        </div>

        {/* Auth card */}
        <div className="relative z-10 w-full flex justify-end">
          <Auth />
        </div>
      </main>
    </div>
  );
}

// ── Protected Route: validates session with server before rendering ──
function ProtectedRoute({ children }) {
  const [status, setStatus] = useState('checking'); // 'checking' | 'ok' | 'unauth'

  useEffect(() => {
    const handleLogout = () => {
      clearTokens();
      localStorage.removeItem('session_id');
      localStorage.removeItem('user');
      setStatus('unauth');
    };
    window.addEventListener('auth:logout', handleLogout);
    
    const sessionId = localStorage.getItem('session_id');
    if (!sessionId) {
      setStatus('unauth');
      return;
    }
    authAPI.me()
      .then(res => res.json())
      .then(() => setStatus('ok'))
      .catch(() => {
        handleLogout();
      });
    
    return () => window.removeEventListener('auth:logout', handleLogout);
  }, []);

  if (status === 'checking') {
    return (
      <div className="min-h-screen bg-background iridescent-bg flex items-center justify-center">
        <svg className="animate-spin w-8 h-8 text-primary" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      </div>
    );
  }

  if (status === 'unauth') {
    return <Navigate to="/" replace />;
  }

  return children;
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AuthPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/onboarding"
            element={
              <ProtectedRoute>
                <Onboarding />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
