import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[SAAITA ErrorBoundary]', error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background iridescent-bg flex items-center justify-center font-body p-8">
          <div className="text-center max-w-md">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-6">
              <svg viewBox="0 0 24 24" className="w-8 h-8 fill-current text-primary">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
              </svg>
            </div>
            <h1 className="text-2xl font-headline font-black text-on-surface mb-2 tracking-tight">
              Something went wrong
            </h1>
            <p className="text-on-surface-variant font-body text-sm mb-6 leading-relaxed">
              SAAITA encountered an unexpected error. This has been noted.
            </p>
            {this.state.error && (
              <pre className="text-left text-xs bg-black/5 rounded-xl p-4 mb-6 overflow-auto text-on-surface-variant max-h-32">
                {this.state.error.message}
              </pre>
            )}
            <button
              onClick={this.handleReset}
              className="px-6 py-3 bg-gradient-to-r from-primary to-secondary text-white font-headline font-black tracking-widest uppercase text-xs rounded-full hover:shadow-xl hover:shadow-primary/30 transition-all"
            >
              Return to Home
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
