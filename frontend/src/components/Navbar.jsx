import React, { useState } from 'react';
import { clearTokens } from '../services/api';

const GOAL_LABELS = {
  finance: "Managing Education Finances",
  academics: "Acing Academics",
  career: "Career Readiness",
  scholarships: "Scholarships / Grants"
};

const JOURNEY_LABELS = {
  ug: "Undergraduate", pg: "Graduate (PG)", pro: "Working Professional"
};

const CONFIDENCE_COLORS = {
  beginner: "#f59e0b", intermediate: "#10b981", expert: "#9f4042"
};

const CONFIDENCE_LABELS = {
  beginner: "Needs guidance", intermediate: "Basics sorted", expert: "Finance pro"
};

const Navbar = ({ activeView, setActiveView, user, onLogout }) => {
    const [showProfile, setShowProfile] = useState(false);

    const initials = user?.full_name
        ? user.full_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
        : '?';

    const answers = (() => {
        try {
            const raw = user?.onboarding_data;
            if (!raw) return {};
            const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
            return parsed.answers || parsed || {};
        } catch { return {}; }
    })();

    // Render drawer via standard fixed positioning
    const drawer = showProfile ? (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 z-[9998]"
                onClick={() => setShowProfile(false)}
            />

            {/* Left Compact Card */}
            <div style={{
                position: 'fixed',
                left: '16px',
                top: '76px',
                zIndex: 9999,
                width: '220px',
            }} className="glass-panel rounded-3xl shadow-2xl border border-white/40 overflow-hidden">

                {/* Header */}
                <div className="p-4 bg-gradient-to-br from-primary/10 to-secondary/10 border-b border-white/20">
                    <div className="flex items-center gap-2.5">
                        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white font-headline font-black text-xs shadow-md shadow-primary/20">
                            {initials}
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="font-headline font-black text-on-surface text-sm truncate">{user?.full_name}</p>
                            <p className="font-body text-on-surface-variant text-[11px] truncate">{user?.email}</p>
                        </div>
                    </div>
                </div>

                {/* Stats */}
                <div className="px-4 py-3 space-y-3">
                    {answers.journey && (
                        <div className="flex flex-col gap-0.5">
                            <span className="text-[9px] font-label font-bold tracking-widest text-on-surface-variant uppercase">Stage</span>
                            <span className="text-xs font-headline font-bold text-on-surface">{JOURNEY_LABELS[answers.journey] || answers.journey}</span>
                        </div>
                    )}
                    {answers.goal && (
                        <div className="flex flex-col gap-0.5">
                            <span className="text-[9px] font-label font-bold tracking-widest text-on-surface-variant uppercase">Goal</span>
                            <span className="text-xs font-headline font-bold text-on-surface">{GOAL_LABELS[answers.goal] || answers.goal}</span>
                        </div>
                    )}
                    {answers.confidence && (
                        <div className="flex flex-col gap-0.5">
                            <span className="text-[9px] font-label font-bold tracking-widest text-on-surface-variant uppercase">Finance</span>
                            <span
                                className="text-xs font-headline font-bold"
                                style={{ color: CONFIDENCE_COLORS[answers.confidence] || 'inherit' }}
                            >
                                {CONFIDENCE_LABELS[answers.confidence] || answers.confidence}
                            </span>
                        </div>
                    )}
                </div>

                {/* Logout */}
                <div className="border-t border-white/20 px-3 py-2">
                    <button
                        onClick={() => {
                            setShowProfile(false);
                            clearTokens();
                            localStorage.removeItem('session_id');
                            localStorage.removeItem('user');
                            onLogout();
                        }}
                        className="w-full flex items-center gap-2 py-2 px-2 text-left text-on-surface-variant hover:text-primary transition-colors text-xs font-body font-semibold rounded-xl hover:bg-primary/10"
                    >
                        <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 fill-current flex-shrink-0">
                            <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" />
                        </svg>
                        Sign out
                    </button>
                </div>
            </div>
        </>
    ) : null;

    return (
        <>
            <nav className="relative z-20 flex items-center justify-between px-6 py-4">

                {/* Brand */}
                <div className="flex items-center gap-2">
                    <span className="font-headline font-black text-primary tracking-widest text-sm uppercase">SAAITA</span>
                </div>

                {/* Tab Switcher */}
                <div className="flex items-center gap-1 bg-white/40 p-1.5 rounded-full backdrop-blur-md shadow-inner border border-white/40">
                    {[
                        { key: 'chat', label: 'Chat' },
                        { key: 'dashboard', label: 'Dashboard' },
                        { key: 'learn', label: 'Learn' },
                    ].map(({ key, label }) => (
                        <button
                            key={key}
                            className={`px-5 py-2 rounded-full text-sm font-headline tracking-wide font-bold transition-all ${
                                activeView === key
                                    ? 'bg-gradient-to-r from-primary to-secondary text-white shadow-lg'
                                    : 'text-on-surface-variant hover:text-on-surface hover:bg-white/30'
                            }`}
                            onClick={() => setActiveView(key)}
                        >
                            {label}
                        </button>
                    ))}
                </div>

                {/* Profile Avatar */}
                <button
                    onClick={() => setShowProfile(prev => !prev)}
                    className={`flex items-center gap-2 p-1.5 pr-3 rounded-full backdrop-blur-md border transition-all ${
                        showProfile
                            ? 'bg-primary/20 border-primary/40'
                            : 'bg-white/40 border-white/40 hover:bg-white/60'
                    }`}
                >
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white font-headline font-black text-xs">
                        {initials}
                    </div>
                    <span className="text-on-surface font-body text-sm font-semibold hidden sm:block max-w-[100px] truncate">
                        {user?.full_name?.split(' ')[0] || 'User'}
                    </span>
                    <svg viewBox="0 0 24 24" className={`w-4 h-4 fill-current text-on-surface-variant transition-transform duration-200 ${showProfile ? 'rotate-180' : ''}`}>
                        <path d="M7 10l5 5 5-5z" />
                    </svg>
                </button>
            </nav>

            {/* Portal drawer — rendered into document.body, escapes all parent constraints */}
            {drawer}
        </>
    );
};

export default Navbar;
