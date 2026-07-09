import React from 'react';
import { Brain } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const ChatWindow = ({ messages, loading, messagesEndRef }) => {
  return (
    <div className="chat-window">
      {messages.length === 0 ? (
        <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted)' }}>
          <Brain size={64} style={{ opacity: 0.2, margin: '0 auto 1rem' }} />
          <h2 style={{ color: 'var(--text-main)', marginBottom: '0.5rem' }}>How can I help with your research today?</h2>
          <p>Upload a document or ask a question to begin.</p>
        </div>
      ) : (
        messages.map((m, i) => (
          <div key={i} className={`message ${m.role === 'human' || m.role === 'user' ? 'user' : 'ai'} animate-fade-in`}>
            {m.role === 'human' || m.role === 'user' ? (
              m.content
            ) : (
              <ReactMarkdown>{m.content}</ReactMarkdown>
            )}
          </div>
        ))
      )}
      {loading && (
        <div className="message ai animate-fade-in" style={{ display: 'flex', gap: '0.5rem' }}>
          <div style={{ width: '8px', height: '8px', background: 'var(--text-muted)', borderRadius: '50%', animation: 'fadeIn 1s infinite alternate' }} />
          <div style={{ width: '8px', height: '8px', background: 'var(--text-muted)', borderRadius: '50%', animation: 'fadeIn 1s infinite alternate 0.2s' }} />
          <div style={{ width: '8px', height: '8px', background: 'var(--text-muted)', borderRadius: '50%', animation: 'fadeIn 1s infinite alternate 0.4s' }} />
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default ChatWindow;
