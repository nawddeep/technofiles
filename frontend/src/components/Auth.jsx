import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, setTokens } from '../services/api';

const EMAIL_REGEX = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;

function validateForm({ isLogin, fullName, email, password, confirmPassword }) {
  const errors = {};
  if (!isLogin && !fullName.trim()) {
    errors.fullName = "Full name is required.";
  }
  if (!email.trim()) {
    errors.email = "Email is required.";
  } else if (!EMAIL_REGEX.test(email)) {
    errors.email = "Enter a valid email address.";
  }
  if (!password) {
    errors.password = "Password is required.";
  } else if (password.length < 12) {
    errors.password = "Password must be at least 12 characters.";
  } else if (!/[A-Z]/.test(password)) {
    errors.password = "Password must contain an uppercase letter.";
  } else if (!/[a-z]/.test(password)) {
    errors.password = "Password must contain a lowercase letter.";
  } else if (!/\d/.test(password)) {
    errors.password = "Password must contain a number.";
  } else if (!/[!@#$%^&*()_+\-=\[\]{}|;:'",./<>?`~]/.test(password)) {
    errors.password = "Password must contain a special character (!@#$%^&*).";
  }
  if (!isLogin) {
    if (!confirmPassword) {
      errors.confirmPassword = "Please confirm your password.";
    } else if (password && confirmPassword !== password) {
      errors.confirmPassword = "Passwords do not match.";
    }
  }
  return errors;
}

export default function Auth() {
  const navigate = useNavigate();
  const [isLogin, setIsLogin] = useState(false);
  const [formData, setFormData] = useState({
    fullName: '', email: '', password: '', confirmPassword: ''
  });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: '' }));
    setServerError('');
  };

  const switchTab = (login) => {
    setIsLogin(login);
    setErrors({});
    setServerError('');
    setFormData({ fullName: '', email: '', password: '', confirmPassword: '' });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');

    const validationErrors = validateForm({ isLogin, ...formData });
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setLoading(true);
    try {
      let res;
      if (isLogin) {
        res = await authAPI.login({ email: formData.email, password: formData.password });
      } else {
        res = await authAPI.signup({
          fullName: formData.fullName,
          email: formData.email,
          password: formData.password
        });
      }
      
      if (!res.ok) {
        const errorData = await res.json();
        setServerError(errorData.error || 'Request failed');
        setLoading(false);
        return;
      }

      const resData = await res.json();
      console.log('[Auth] Response:', resData);
      
      // Save tokens
      if (resData.access_token && resData.csrf_token) {
        setTokens(resData.access_token, resData.refresh_token, resData.csrf_token);
        localStorage.setItem('session_id', resData.user?.id || 'session');
        localStorage.setItem('user', JSON.stringify(resData.user));
      }
      
      if (resData.user && resData.user.is_onboarded) {
        navigate('/dashboard');
      } else {
        navigate('/onboarding');
      }
    } catch (err) {
      console.error('[Auth] Error:', err);
      setServerError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="w-full md:w-1/2 relative flex items-center justify-center p-8 overflow-hidden z-10">
      <div className="absolute top-0 right-0 w-80 h-80 bg-secondary/10 aurora-blur rounded-full"></div>
      <div className="absolute bottom-0 left-0 w-64 h-64 bg-primary/10 aurora-blur rounded-full"></div>

      <div className="w-full max-w-[420px] glass-panel p-8 rounded-3xl relative z-10">
        {/* Tabs */}
        <div className="flex gap-8 mb-6 border-b border-black/5 relative z-10">
          <button
            type="button"
            onClick={() => switchTab(false)}
            className={`pb-2 tracking-wide font-headline text-[15px] transition-all ${!isLogin ? 'text-primary font-bold border-b-2 border-primary' : 'text-on-surface-variant font-semibold hover:text-on-surface'}`}
          >
            SIGNUP
          </button>
          <button
            type="button"
            onClick={() => switchTab(true)}
            className={`pb-2 tracking-wide font-headline text-[15px] transition-all ${isLogin ? 'text-primary font-bold border-b-2 border-primary' : 'text-on-surface-variant font-semibold hover:text-on-surface'}`}
          >
            LOGIN
          </button>
        </div>

        {/* Server error banner */}
        {serverError && (
          <div className="mb-4 px-4 py-2.5 bg-red-500/10 border border-red-400/30 rounded-xl text-red-600 text-xs font-semibold tracking-wide">
            {serverError}
          </div>
        )}

        <form className="space-y-5 relative z-10" onSubmit={handleSubmit} noValidate>

          {/* Full Name (signup only) */}
          {!isLogin && (
            <div className="space-y-1">
              <label className="font-label text-[10px] text-primary font-bold tracking-widest uppercase block ml-1">Full Name</label>
              <input
                className={`w-full bg-transparent border-0 border-b py-2 px-1 text-on-surface placeholder:text-outline-variant focus:ring-0 transition-colors duration-300 font-headline tracking-tight text-base uppercase ${errors.fullName ? 'border-red-400' : 'border-black/10 focus:border-primary'}`}
                placeholder="ELARA VANCE"
                type="text"
                value={formData.fullName}
                onChange={(e) => handleChange('fullName', e.target.value)}
              />
              {errors.fullName && <p className="text-red-500 text-[10px] font-semibold ml-1">{errors.fullName}</p>}
            </div>
          )}

          {/* Email */}
          <div className="space-y-1">
            <label className="font-label text-[10px] text-primary font-bold tracking-widest uppercase block ml-1">Email Address</label>
            <input
              className={`w-full bg-transparent border-0 border-b py-2 px-1 text-on-surface placeholder:text-outline-variant focus:ring-0 transition-colors duration-300 font-headline tracking-tight text-base uppercase ${errors.email ? 'border-red-400' : 'border-black/10 focus:border-primary'}`}
              placeholder="VANCE@ETHEREAL.IO"
              type="email"
              value={formData.email}
              onChange={(e) => handleChange('email', e.target.value)}
            />
            {errors.email && <p className="text-red-500 text-[10px] font-semibold ml-1">{errors.email}</p>}
          </div>

          {/* Password */}
          <div className="space-y-1">
            <label className="font-label text-[10px] text-primary font-bold tracking-widest uppercase block ml-1">Secret Key</label>
            <input
              className={`w-full bg-transparent border-0 border-b py-2 px-1 text-on-surface placeholder:text-outline-variant focus:ring-0 transition-colors duration-300 font-headline tracking-tight text-base ${errors.password ? 'border-red-400' : 'border-black/10 focus:border-primary'}`}
              placeholder="••••••••••••"
              type="password"
              value={formData.password}
              onChange={(e) => handleChange('password', e.target.value)}
            />
            {errors.password && <p className="text-red-500 text-[10px] font-semibold ml-1">{errors.password}</p>}
          </div>

          {/* Confirm Password (signup only) */}
          {!isLogin && (
            <div className="space-y-1">
              <label className="font-label text-[10px] text-primary font-bold tracking-widest uppercase block ml-1">Confirm Key</label>
              <input
                className={`w-full bg-transparent border-0 border-b py-2 px-1 text-on-surface placeholder:text-outline-variant focus:ring-0 transition-colors duration-300 font-headline tracking-tight text-base ${errors.confirmPassword ? 'border-red-400' : 'border-black/10 focus:border-primary'}`}
                placeholder="••••••••••••"
                type="password"
                value={formData.confirmPassword}
                onChange={(e) => handleChange('confirmPassword', e.target.value)}
              />
              {errors.confirmPassword && <p className="text-red-500 text-[10px] font-semibold ml-1">{errors.confirmPassword}</p>}
            </div>
          )}

          {/* Submit */}
          <div className="pt-3">
            <button
              className="w-full bg-gradient-to-r from-primary via-primary-dim to-secondary py-3.5 rounded-full text-on-primary font-black tracking-[0.2em] uppercase text-xs hover:shadow-xl hover:shadow-primary/30 active:scale-[0.98] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              type="submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                  </svg>
                  {isLogin ? 'ENTERING...' : 'CREATING...'}
                </>
              ) : (
                isLogin ? 'ENTER HORIZON' : 'CREATE IDENTITY'
              )}
            </button>
          </div>

          {/* OR divider */}
          <div className="flex items-center gap-4 opacity-50">
            <div className="flex-1 h-px bg-black/20"></div>
            <span className="font-label text-[10px] font-bold tracking-widest text-on-surface-variant">OR</span>
            <div className="flex-1 h-px bg-black/20"></div>
          </div>

          {/* Social buttons */}
          <div className="space-y-2">
            {[
              {
                label: "Continue with Google",
                icon: (
                  <svg viewBox="0 0 24 24" className="w-3.5 h-3.5">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                )
              },
              {
                label: "Continue with Apple",
                icon: (
                  <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]" fill="white">
                    <path d="M16.59 13.91C16.59 10.87 19.06 9.38 19.18 9.31C17.78 7.26 15.63 6.94 14.91 6.84C13.25 6.67 11.66 7.82 10.81 7.82C9.94 7.82 8.63 6.85 7.24 6.88C5.46 6.9 3.82 7.91 2.89 9.53C1.02 12.8 2.41 17.65 4.23 20.28C5.12 21.56 6.16 23.01 7.55 22.96C8.89 22.91 9.4 22.1 11.02 22.1C12.63 22.1 13.09 23 14.48 22.96C15.9 22.91 16.8 21.6 17.68 20.31C18.7 18.82 19.12 17.38 19.15 17.3C19.12 17.27 16.59 16.3 16.59 13.91ZM13.88 4.67C14.62 3.77 15.12 2.51 14.99 1.25C13.91 1.29 12.57 1.97 11.81 2.87C11.13 3.67 10.53 4.96 10.68 6.19C11.88 6.28 13.14 5.57 13.88 4.67Z"/>
                  </svg>
                )
              },
              {
                label: "Continue with phone",
                icon: (
                  <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
                  </svg>
                )
              }
            ].map(({ label, icon }) => (
              <button
                key={label}
                type="button"
                onClick={() => setServerError(`${label} is coming soon.`)}
                className="w-full flex items-center justify-center gap-2 py-2 bg-[#2d2d2d]/90 backdrop-blur-md rounded-full border border-white/10 hover:bg-[#3d3d3d] active:scale-[0.98] transition-all"
              >
                {icon}
                <span className="font-body font-semibold text-white tracking-wide text-xs">{label}</span>
              </button>
            ))}
          </div>

        </form>
      </div>
    </section>
  );
}
