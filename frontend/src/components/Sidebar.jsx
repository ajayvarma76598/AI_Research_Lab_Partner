import React from 'react';
import { Brain, LogOut, MessageSquare } from 'lucide-react';

const Sidebar = ({ 
  user, 
  logout, 
  sessions, 
  documents, 
  activeDocuments, 
  activeSession, 
  setActiveSession, 
  setMessages, 
  loadSession, 
  toggleDocument, 
  fileInputRef, 
  handleFileUpload 
}) => {
  return (
    <div className="sidebar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
        <Brain size={32} color="var(--primary)" />
        <h2 style={{ fontSize: '18px' }}>Research AI</h2>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <label style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Active Documents (Max 5)</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', maxHeight: '200px', overflowY: 'auto' }}>
          {documents.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No documents uploaded.</div>
          ) : (
            documents.map(doc => (
              <label key={doc.document_id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '13px', cursor: 'pointer', padding: '0.25rem 0' }}>
                <input 
                  type="checkbox" 
                  checked={activeDocuments.includes(doc.document_id)}
                  onChange={() => toggleDocument(doc.document_id)}
                />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.title}</span>
              </label>
            ))
          )}
        </div>
        
        <input 
          type="file" 
          accept=".pdf" 
          style={{ display: 'none' }} 
          ref={fileInputRef}
          onChange={handleFileUpload}
        />
      </div>

      <button className="btn-primary" onClick={() => { setActiveSession(null); setMessages([]) }} style={{ marginBottom: '2rem' }}>
        + New Chat
      </button>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <h3 style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.5rem', flexShrink: 0 }}>Your History</h3>
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem', flex: 1, paddingRight: '4px' }}>
          {sessions.map(s => (
            <button
              key={s.thread_id}
              className="btn-icon"
              onClick={() => loadSession(s.thread_id)}
              style={{
                justifyContent: 'flex-start',
                padding: '0.75rem',
                width: '100%',
                background: activeSession === s.thread_id ? 'rgba(255,255,255,0.1)' : 'transparent',
                color: 'var(--text-main)',
                flexShrink: 0
              }}
            >
              <MessageSquare size={16} />
              <span style={{ marginLeft: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {s.title}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--surface-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <img src={user?.picture || 'https://via.placeholder.com/32'} alt="Profile" style={{ width: '32px', height: '32px', borderRadius: '50%' }} />
          <div style={{ fontSize: '13px' }}>
            <div style={{ fontWeight: 600 }}>{user?.name || 'Researcher'}</div>
          </div>
        </div>
        <button className="btn-icon" onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}>
          <LogOut size={16} />
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
