import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGetMe, apiLogout } from '../services/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGetMe()
      .then(data => {
        if (!data.user.is_onboarded) {
          navigate('/onboarding', { replace: true });
        } else {
          setUser(data.user);
        }
      })
      .catch(() => {
        navigate('/', { replace: true });
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleLogout = async () => {
    await apiLogout();
    navigate('/', { replace: true });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <svg className="animate-spin w-8 h-8 text-primary" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
      </div>
    );
  }

  if (!user) return null;

  const initials = user.full_name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  // Format member since date nicely
  const memberSince = user.member_since
    ? new Date(user.member_since).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
    : '—';

  return (
    <div className="min-h-screen iridescent-bg font-body text-on-surface relative overflow-hidden">
      <div className="absolute top-0 left-0 w-96 h-96 bg-primary/10 aurora-blur rounded-full pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-80 h-80 bg-secondary/10 aurora-blur rounded-full pointer-events-none" />

      {/* Navbar */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-5 border-b border-black/5">
        <span className="font-headline font-black text-xl tracking-tight text-on-surface">
          SAAI<span className="text-primary">TA</span>
        </span>
        <button
          onClick={handleLogout}
          className="text-xs font-bold tracking-widest uppercase text-on-surface-variant hover:text-primary transition-colors"
        >
          Logout
        </button>
      </nav>

      {/* Content */}
      <main className="relative z-10 max-w-2xl mx-auto px-8 py-16">

        {/* Welcome card */}
        <div className="glass-panel p-10 rounded-3xl mb-8">
          <div className="flex items-center gap-6">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white font-headline font-black text-xl flex-shrink-0">
              {initials}
            </div>
            <div>
              <p className="font-label text-[10px] text-primary font-bold tracking-widest uppercase mb-1">Welcome back</p>
              <h1 className="font-headline text-2xl font-black text-on-surface tracking-tight">{user.full_name}</h1>
              <p className="font-body text-sm text-on-surface-variant mt-0.5">{user.email}</p>
            </div>
          </div>
        </div>

        {/* Real stats from backend */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: "Member Since", value: memberSince },
            { label: "Active Sessions", value: String(user.active_sessions ?? 1) },
            { label: "User ID", value: `#${user.id}` },
          ].map(({ label, value }) => (
            <div key={label} className="glass-panel p-5 rounded-2xl text-center">
              <p className="font-label text-[9px] text-primary font-bold tracking-widest uppercase mb-1">{label}</p>
              <p className="font-headline font-black text-base text-on-surface leading-tight">{value}</p>
            </div>
          ))}
        </div>

        {/* Account details */}
        <div className="glass-panel p-8 rounded-3xl">
          <p className="font-label text-[10px] text-primary font-bold tracking-widest uppercase mb-4">Account Details</p>
          <div className="space-y-4">
            {[
              { field: "Full Name", val: user.full_name },
              { field: "Email Address", val: user.email },
              { field: "Member Since", val: memberSince },
            ].map(({ field, val }) => (
              <div key={field} className="flex items-center justify-between py-3 border-b border-black/5 last:border-0">
                <span className="font-label text-xs text-on-surface-variant font-semibold tracking-wide">{field}</span>
                <span className="font-headline text-sm font-bold text-on-surface">{val}</span>
              </div>
            ))}
          </div>
        </div>

      </main>
    </div>
  );
}
