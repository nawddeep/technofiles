import React from 'react';

const GOAL_LABELS = {
  finance: "Managing Education Finances",
  academics: "Acing Academics",
  career: "Career Readiness",
  scholarships: "Finding Scholarships / Grants"
};

const JOURNEY_LABELS = {
  ug: "Undergraduate",
  pg: "Graduate (PG)",
  pro: "Working Professional"
};

const CONFIDENCE_LABELS = {
  beginner: "Still learning — needs guidance",
  intermediate: "Basics sorted",
  expert: "Financial pro"
};

const CONFIDENCE_COLORS = {
  beginner: "text-amber-500",
  intermediate: "text-emerald-500",
  expert: "text-primary"
};

function StatCard({ icon, label, value, sub }) {
  return (
    <div className="glass-panel rounded-2xl p-5 flex flex-col gap-2 hover:-translate-y-1 transition-transform duration-300">
      <div className="flex items-center gap-2 text-on-surface-variant text-xs font-label font-bold tracking-widest uppercase">
        <span className="text-lg">{icon}</span>
        {label}
      </div>
      <p className="text-2xl font-headline font-black text-on-surface tracking-tight">{value}</p>
      {sub && <p className="text-xs text-on-surface-variant font-body">{sub}</p>}
    </div>
  );
}

export default function DashboardHome({ user, onNavigate }) {
  const answers = (() => {
    try {
      const raw = user?.onboarding_data;
      if (!raw) return {};
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
      return parsed.answers || parsed || {};
    } catch {
      return {};
    }
  })();

  const firstName = user?.full_name?.split(' ')[0] || 'there';
  const memberSince = user?.member_since || '—';

  const journey = JOURNEY_LABELS[answers.journey] || '—';
  const goal = GOAL_LABELS[answers.goal] || '—';
  const confidence = answers.confidence || 'beginner';

  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-8 flex flex-col gap-8">

      {/* Welcome Banner */}
      <div className="glass-panel rounded-3xl p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <p className="text-on-surface-variant text-sm font-body mb-1">Welcome back,</p>
          <h1 className="text-3xl md:text-4xl font-headline font-black text-on-surface tracking-tight text-glow">
            {firstName} 👋
          </h1>
          <p className="text-on-surface-variant text-xs font-body mt-2">Member since {memberSince}</p>
        </div>

        <div className="flex gap-3 flex-wrap">
          <button
            onClick={() => onNavigate('chat')}
            className="px-5 py-2.5 bg-gradient-to-r from-primary to-secondary text-white font-headline font-bold text-sm rounded-full hover:shadow-lg hover:shadow-primary/30 active:scale-[0.98] transition-all"
          >
            Ask SAAITA
          </button>
          <button
            onClick={() => onNavigate('learn')}
            className="px-5 py-2.5 border border-primary/30 text-primary font-headline font-bold text-sm rounded-full hover:bg-primary/10 active:scale-[0.98] transition-all"
          >
            View Learning Path
          </button>
        </div>
      </div>

      {/* Profile Stats */}
      <div>
        <h2 className="text-xs font-label font-bold tracking-widest uppercase text-on-surface-variant mb-4">Your Profile</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard
            icon="🎓"
            label="Academic Stage"
            value={journey}
            sub={answers.sub_journey ? `Year / Focus: ${answers.sub_journey}` : undefined}
          />
          <StatCard
            icon="🎯"
            label="Primary Goal"
            value={goal}
          />
          <StatCard
            icon="💡"
            label="Finance Confidence"
            value={
              <span className={`text-2xl font-headline font-black tracking-tight ${CONFIDENCE_COLORS[confidence] || 'text-on-surface'}`}>
                {CONFIDENCE_LABELS[confidence] || '—'}
              </span>
            }
          />
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-xs font-label font-bold tracking-widest uppercase text-on-surface-variant mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

          <button
            onClick={() => onNavigate('chat')}
            className="glass-panel rounded-2xl p-5 text-left group hover:-translate-y-1 transition-all duration-300 hover:shadow-lg"
          >
            <div className="text-2xl mb-3">💬</div>
            <h3 className="font-headline font-bold text-on-surface text-base group-hover:text-primary transition-colors">
              Chat with SAAITA
            </h3>
            <p className="text-on-surface-variant text-xs font-body mt-1">
              Ask about finances, scholarships, career paths, or get a personalized study plan.
            </p>
          </button>

          <button
            onClick={() => onNavigate('learn')}
            className="glass-panel rounded-2xl p-5 text-left group hover:-translate-y-1 transition-all duration-300 hover:shadow-lg"
          >
            <div className="text-2xl mb-3">🗺️</div>
            <h3 className="font-headline font-bold text-on-surface text-base group-hover:text-primary transition-colors">
              Explore Learning Paths
            </h3>
            <p className="text-on-surface-variant text-xs font-body mt-1">
              Browse structured roadmaps for any skill — Beginner, Intermediate, and Advanced.
            </p>
          </button>

        </div>
      </div>

      {/* Tips */}
      <div className="glass-panel rounded-2xl p-5 border-l-4 border-primary">
        <p className="text-xs font-label font-bold tracking-widest uppercase text-primary mb-2">💡 SAAITA Tip</p>
        <p className="text-on-surface-variant text-sm font-body leading-relaxed">
          {answers.goal === 'finance'
            ? "Try asking SAAITA to create a monthly budget plan based on your income and expenses. Be specific — include your actual numbers for the best advice."
            : answers.goal === 'career'
            ? "Ask SAAITA for a step-by-step career roadmap in your field. Include your current skills and target role for a personalized path."
            : answers.goal === 'scholarships'
            ? "Tell SAAITA your academic scores, location, and course — it can suggest specific scholarships and how to apply."
            : "Ask SAAITA to help you build a weekly study schedule. Share your subjects, deadlines, and available hours."}
        </p>
      </div>

    </div>
  );
}
