import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Gap-to-Brief UI caught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: '40px',
            backgroundColor: '#090d16',
            color: '#f8fafc',
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'sans-serif',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              backgroundColor: '#ef444422',
              color: '#ef4444',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '24px',
              marginBottom: '16px',
            }}
          >
            &times;
          </div>
          <h2 style={{ color: '#f8fafc', fontSize: '20px', marginBottom: '8px' }}>
            UI Component Exception
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '14px', maxWidth: '500px', marginBottom: '20px' }}>
            A client-side error occurred while rendering the page. Details below:
          </p>
          <pre
            style={{
              backgroundColor: '#1e293b',
              padding: '16px 24px',
              borderRadius: '8px',
              maxWidth: '800px',
              overflow: 'auto',
              color: '#fca5a5',
              fontSize: '13px',
              textAlign: 'left',
              border: '1px solid #334155',
            }}
          >
            {this.state.error?.stack || this.state.error?.message || 'Unknown runtime error'}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '24px',
              padding: '10px 24px',
              backgroundColor: '#0284c7',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '14px',
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
