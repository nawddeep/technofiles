import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Auth from './components/Auth';
import Dashboard from './pages/Dashboard';
import Onboarding from './pages/Onboarding';

function AuthPage() {
  return (
    <div className="bg-background iridescent-bg text-on-background font-body min-h-screen overflow-hidden selection:bg-primary selection:text-on-primary">
      <main className="flex min-h-screen w-full relative">
        {/* Full Screen Background Video */}
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
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent to-black/30 opacity-90"></div>
          {/* Aurora blobs */}
          <div className="absolute top-1/4 -left-20 w-80 h-80 bg-primary-dim/30 aurora-blur rounded-full"></div>
          <div className="absolute bottom-1/4 right-0 w-96 h-96 bg-secondary/20 aurora-blur rounded-full"></div>
        </div>

        {/* Auth card aligned right */}
        <div className="relative z-10 w-full flex justify-end">
          <Auth />
        </div>
      </main>
    </div>
  );
}

function ProtectedRoute({ children }) {
  const sessionId = localStorage.getItem('session_id');
  if (!sessionId) {
    return <Navigate to="/" replace />;
  }
  return children;
}

function App() {
  return (
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
        {/* Catch all unknown routes */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
