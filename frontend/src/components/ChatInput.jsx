import React from 'react';
import { Upload, Send, Link as LinkIcon, Plus } from 'lucide-react';

const ChatInput = ({ 
  input, 
  setInput, 
  loading, 
  uploading, 
  ingestingUrl, 
  sendMessage, 
  showMenu, 
  setShowMenu, 
  handleUrlIngest, 
  fileInputRef, 
  menuRef 
}) => {
  return (
    <div className="input-area" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {(uploading || ingestingUrl) && (
        <div style={{ fontSize: '12px', color: 'var(--primary-light)', paddingLeft: '1rem' }}>
          {uploading ? "Uploading document..." : "Fetching from URL..."}
        </div>
      )}
      <form onSubmit={sendMessage} className="chat-input-wrapper" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--surface)', padding: '0.75rem 1.25rem', borderRadius: '24px', border: '1px solid var(--surface-border)', boxShadow: '0 4px 24px rgba(0,0,0,0.2)' }}>
        <div className="attachment-menu-container" ref={menuRef} style={{ position: 'relative' }}>
          <button 
            type="button" 
            className="icon-btn" 
            style={{ background: 'rgba(255,255,255,0.05)', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0.5rem', borderRadius: '50%' }}
            onClick={() => setShowMenu(!showMenu)} 
            disabled={uploading || ingestingUrl}
            title="Add Attachment"
          >
            <Plus size={20} />
          </button>

          {showMenu && (
            <div style={{ 
              position: 'absolute', bottom: '100%', left: '0', marginBottom: '1rem', 
              background: 'var(--surface)', border: '1px solid var(--surface-border)', 
              borderRadius: '8px', padding: '0.5rem', display: 'flex', flexDirection: 'column', 
              gap: '0.25rem', minWidth: '160px', zIndex: 10, boxShadow: '0 8px 24px rgba(0,0,0,0.4)' 
            }}>
              <button type="button" onClick={() => { fileInputRef.current?.click(); setShowMenu(false); }} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem', background: 'transparent', border: 'none', color: 'var(--text-main)', cursor: 'pointer', textAlign: 'left', borderRadius: '4px' }} className="menu-item">
                <Upload size={16} /> Upload PDF
              </button>
              <button type="button" onClick={() => {
                setShowMenu(false);
                const url = prompt("Enter PDF URL to fetch (e.g. ArXiv link):");
                if (url) handleUrlIngest(null, url);
              }} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem', background: 'transparent', border: 'none', color: 'var(--text-main)', cursor: 'pointer', textAlign: 'left', borderRadius: '4px' }} className="menu-item">
                <LinkIcon size={16} /> Fetch from URL
              </button>
            </div>
          )}
        </div>
        
        <input 
          type="text" 
          placeholder="Ask a question or attach a document..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
          style={{ flex: 1, background: 'transparent', border: 'none', color: 'var(--text-main)', outline: 'none', fontSize: '16px', padding: '0.5rem 0' }}
        />
        <button type="submit" className="send-btn" disabled={loading || !input.trim()} style={{ width: '36px', height: '36px' }}>
          <Send size={16} />
        </button>
      </form>
    </div>
  );
};

export default ChatInput;
