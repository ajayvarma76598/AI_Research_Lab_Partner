import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { Brain } from 'lucide-react';

const Login = () => {
  const { loginWithRedirect, isAuthenticated } = useAuth0();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', maxWidth: '400px' }}>
        <Brain size={48} color="var(--primary)" style={{ margin: '0 auto 1.5rem' }} />
        <h1 style={{ marginBottom: '1rem', fontSize: '24px' }}>AI Research Partner</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
          Secure, orchestrator-driven multi-agent analysis for complex research documents.
        </p>
        <button className="btn-primary" onClick={() => loginWithRedirect()} style={{ width: '100%' }}>
          Log In / Sign Up
        </button>
      </div>
    </div>
  );
};

export default Login;
