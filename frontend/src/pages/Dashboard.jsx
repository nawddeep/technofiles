import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, clearTokens } from '../services/api';
import ChatArea from '../components/ChatArea';
import LearningPathUI from '../components/LearningPathUI';
import DashboardHome from '../components/DashboardHome';
import Navbar from '../components/Navbar';

export default function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState('chat');

  useEffect(() => {
    authAPI.me()
      .then(res => res.json())
      .then(data => {
        if (data.user && !data.user.is_onboarded) {
          navigate('/onboarding', { replace: true });
        } else if (data.user) {
          setUser(data.user);
        }
      })
      .catch(() => navigate('/', { replace: true }))
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleLogout = async () => {
    try {
      await authAPI.logout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      clearTokens();
      localStorage.removeItem('session_id');
      localStorage.removeItem('user');
      navigate('/', { replace: true });
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background iridescent-bg flex items-center justify-center">
        <svg className="animate-spin w-8 h-8 text-primary" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="h-screen w-full iridescent-bg font-body text-on-surface relative overflow-hidden flex flex-col">
      {/* Ambient blobs */}
      <div className="absolute top-0 left-0 w-96 h-96 bg-primary/10 aurora-blur rounded-full pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-80 h-80 bg-secondary/10 aurora-blur rounded-full pointer-events-none" />

      {/* Navbar */}
      <Navbar
        activeView={activeView}
        setActiveView={setActiveView}
        user={user}
        onLogout={handleLogout}
      />

      {/* Main Content */}
      <main className="relative z-10 flex-1 w-full mx-auto overflow-y-auto">
        {activeView === 'dashboard' && (
          <DashboardHome user={user} onNavigate={setActiveView} />
        )}
        {activeView === 'chat' && (
          <ChatArea />
        )}
        {activeView === 'learn' && (
          <div className="w-full max-w-4xl mx-auto px-4 py-8">
            <h2 className="text-2xl font-headline font-black text-on-surface mb-4 tracking-tight">
              Learning Paths
            </h2>
            <p className="text-on-surface-variant text-sm font-body mb-8">
              Go to <strong>Chat</strong> and ask SAAITA for a learning roadmap on any topic — it will appear here as an interactive path.
            </p>
            <LearningPathUI data={null} />
          </div>
        )}
      </main>
    </div>
  );
}
