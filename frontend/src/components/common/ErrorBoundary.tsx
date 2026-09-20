import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RotateCcw, RefreshCw } from 'lucide-react';
import { Button } from './Button';

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallbackTitle?: string;
  fallbackSubtitle?: string;
  portalTheme?: 'auditor' | 'hr';
  onReset?: () => void;
  customFallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode);
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo);
  }

  public reset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  public render() {
    if (this.state.hasError) {
      if (typeof this.props.customFallback === 'function') {
        return this.props.customFallback(this.state.error || new Error('Unknown error'), this.reset);
      }
      if (this.props.customFallback) {
        return this.props.customFallback;
      }

      const isAuditor = this.props.portalTheme === 'auditor';
      const title = this.props.fallbackTitle || 'Component Rendering Error';
      const subtitle =
        this.props.fallbackSubtitle ||
        'An unexpected error occurred while rendering this interface section. Other sections remain active.';

      return (
        <div
          role="alert"
          className={`p-6 rounded-xl border flex flex-col gap-4 max-w-2xl my-4 mx-auto ${
            isAuditor
              ? 'bg-linear-surface-1 border-linear-hairline text-linear-ink'
              : 'bg-white border-slate-200 text-slate-900 shadow-sm'
          }`}
        >
          <div className="flex items-start gap-3.5">
            <div
              className={`p-2 rounded-lg shrink-0 ${
                isAuditor
                  ? 'bg-grafana-orange/15 text-grafana-orange'
                  : 'bg-amber-50 text-amber-600 border border-amber-200'
              }`}
            >
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
              <p
                className={`text-xs mt-1 ${
                  isAuditor ? 'text-linear-ink-muted' : 'text-slate-500'
                }`}
              >
                {subtitle}
              </p>
            </div>
          </div>

          {this.state.error && (
            <div
              className={`p-3 rounded-lg text-xs font-mono break-all overflow-x-auto border ${
                isAuditor
                  ? 'bg-linear-surface-2 border-linear-hairline text-grafana-orange'
                  : 'bg-red-50/70 border-red-200 text-red-700'
              }`}
            >
              {this.state.error.message || String(this.state.error)}
            </div>
          )}

          <div
            className={`flex items-center gap-2 pt-2 border-t justify-end ${
              isAuditor ? 'border-linear-hairline' : 'border-slate-200'
            }`}
          >
            <Button
              variant="secondary"
              size="sm"
              portalTheme={this.props.portalTheme || 'hr'}
              onClick={() => window.location.reload()}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Reload Page
            </Button>
            <Button
              variant="primary"
              size="sm"
              portalTheme={this.props.portalTheme || 'hr'}
              onClick={this.reset}
              leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            >
              Try Again
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
