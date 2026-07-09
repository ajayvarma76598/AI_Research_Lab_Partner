import React, { useState, useEffect, useRef } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import axios from 'axios';
import Sidebar from '../components/Sidebar';
import ChatWindow from '../components/ChatWindow';
import ChatInput from '../components/ChatInput';

const Dashboard = () => {
  const { logout, user, getAccessTokenSilently } = useAuth0();
  const [sessions, setSessions] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ingestingUrl, setIngestingUrl] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [activeSession, setActiveSession] = useState(null);
  const [activeDocuments, setActiveDocuments] = useState([]);
  const [showMenu, setShowMenu] = useState(false);
  
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    fetchSessions();
    fetchDocuments();
    
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const getApi = async () => {
    try {
      const token = await getAccessTokenSilently();
      return axios.create({
        baseURL: import.meta.env.VITE_API_BASE_URL,
        headers: { Authorization: `Bearer ${token}` }
      });
    } catch (e) {
      // Graceful fallback for local dev if Auth0 is not fully configured
      return axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL });
    }
  };

  const fetchSessions = async () => {
    const api = await getApi();
    try {
      const res = await api.get('/sessions');
      setSessions(res.data);
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  };

  const fetchDocuments = async () => {
    const api = await getApi();
    try {
      const res = await api.get('/documents');
      setDocuments(res.data);
      if (res.data.length > 0 && activeDocuments.length === 0) {
        setActiveDocuments([res.data[0].document_id]);
      }
    } catch (err) {
      console.error("Failed to fetch documents", err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    const api = await getApi();
    try {
      const res = await api.post('/ingest/document', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      await fetchDocuments();
      setActiveDocuments([res.data.document_id]);
      setMessages(prev => [...prev, { role: 'ai', content: `Successfully ingested ${file.name}! What would you like to know about it?` }]);
    } catch (err) {
      console.error("Upload failed", err);
      alert("Failed to upload document. See console for details.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleUrlIngest = async (e, directUrl = null) => {
    if (e) e.preventDefault();
    const targetUrl = directUrl || urlInput.trim();
    if (!targetUrl) return;

    setIngestingUrl(true);
    const api = await getApi();
    try {
      const res = await api.post('/ingest/url', { url: targetUrl });
      await fetchDocuments();
      setActiveDocuments([res.data.document_id]);
      setMessages(prev => [...prev, { role: 'ai', content: `Successfully ingested document from URL! What would you like to know about it?` }]);
      setUrlInput('');
    } catch (err) {
      console.error("URL Ingest failed", err);
      alert("Failed to ingest from URL. See console for details.");
    } finally {
      setIngestingUrl(false);
    }
  };

  const loadSession = async (threadId) => {
    setActiveSession(threadId);
    const api = await getApi();
    try {
      const res = await api.get(`/sessions/${threadId}/history`);
      setMessages(res.data.messages.map(m => ({
        role: m.role,
        content: m.content
      })));
    } catch (err) {
      console.error("Failed to load history", err);
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'human', content: userMessage }]);
    setLoading(true);

    let currentThreadId = activeSession;
    let isNewSession = false;
    if (!currentThreadId) {
      currentThreadId = crypto.randomUUID();
      setActiveSession(currentThreadId);
      isNewSession = true;
      setSessions(prev => [{
        thread_id: currentThreadId,
        title: "New Chat...",
        updated_at: new Date().toISOString()
      }, ...prev]);
    }

    const api = await getApi();
    try {
      if (activeDocuments.length === 0) {
        // Discovery Mode
        const payload = {
          query: userMessage,
          limit: 5,
          thread_id: currentThreadId
        };
        const res = await api.post('/discover', payload);
        
        let answer = `I found ${res.data.results.length} papers related to your query:\n\n`;
        res.data.results.forEach((paper, i) => {
          answer += `**${i+1}. ${paper.title}**\n`;
          answer += `*Authors: ${paper.authors.join(", ")}*\n`;
          if (paper.pdf_url) {
            answer += `[Read PDF](${paper.pdf_url})\n`;
          }
          answer += `\n`;
        });
        
        setMessages(prev => [...prev, { role: 'ai', content: answer }]);
        
        if (isNewSession) fetchSessions();
      } else if (activeDocuments.length === 1) {
        const payload = {
          document_id: activeDocuments[0],
          question: userMessage,
          thread_id: currentThreadId
        };
        
        // Add placeholder AI message
        setMessages(prev => [...prev, { role: 'ai', content: '' }]);
        
        const token = await getAccessTokenSilently().catch(() => null);
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/query/stream`, {
          method: 'POST',
          headers: headers,
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          let errorDetail = 'Server returned ' + response.status;
          try {
            const errData = await response.json();
            if (errData.detail) {
              if (Array.isArray(errData.detail)) {
                errorDetail = errData.detail[0].msg.replace("Value error, ", "");
              } else {
                errorDetail = errData.detail;
              }
            }
          } catch (e) {}
          throw new Error(errorDetail);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let aiMessage = '';
        let buffer = '';
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop(); // keep the incomplete chunk in the buffer
          
          for (const chunk of parts) {
            let eventType = 'message';
            let dataStr = '';
            
            for (const line of chunk.split('\n')) {
              if (line.startsWith('event: ')) eventType = line.substring(7).trim();
              else if (line.startsWith('data: ')) dataStr = line.substring(6);
            }
            
            if (dataStr) {
              try {
                const data = JSON.parse(dataStr);
                if (eventType === 'message') {
                  aiMessage += data.content;
                  setMessages(prev => {
                    const newMsgs = [...prev];
                    newMsgs[newMsgs.length - 1].content = aiMessage;
                    return newMsgs;
                  });
                } else if (eventType === 'metadata') {
                  if (isNewSession) fetchSessions();
                } else if (eventType === 'error') {
                  throw new Error(data.detail);
                }
              } catch (e) {
                if (eventType === 'error') throw e; // Rethrow actual backend errors
                console.warn("Failed to parse SSE chunk:", dataStr);
              }
            }
          }
        }

      } else {
        const payload = {
          document_ids: activeDocuments,
          question: userMessage,
          thread_id: currentThreadId
        };
        
        // Add placeholder AI message
        setMessages(prev => [...prev, { role: 'ai', content: '' }]);
        
        const token = await getAccessTokenSilently().catch(() => null);
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/compare/stream`, {
          method: 'POST',
          headers: headers,
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          let errorDetail = 'Server returned ' + response.status;
          try {
            const errData = await response.json();
            if (errData.detail) {
              if (Array.isArray(errData.detail)) {
                errorDetail = errData.detail[0].msg.replace("Value error, ", "");
              } else {
                errorDetail = errData.detail;
              }
            }
          } catch (e) {}
          throw new Error(errorDetail);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let aiMessage = '';
        let buffer = '';
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop();
          
          for (const chunk of parts) {
            let eventType = 'message';
            let dataStr = '';
            
            for (const line of chunk.split('\n')) {
              if (line.startsWith('event: ')) eventType = line.substring(7).trim();
              else if (line.startsWith('data: ')) dataStr = line.substring(6);
            }
            
            if (dataStr) {
              try {
                const data = JSON.parse(dataStr);
                if (eventType === 'message') {
                  aiMessage += data.content;
                  setMessages(prev => {
                    const newMsgs = [...prev];
                    newMsgs[newMsgs.length - 1].content = aiMessage;
                    return newMsgs;
                  });
                } else if (eventType === 'metadata') {
                  if (isNewSession) fetchSessions();
                } else if (eventType === 'error') {
                  throw new Error(data.detail);
                }
              } catch (e) {
                if (eventType === 'error') throw e;
                console.warn("Failed to parse SSE chunk:", dataStr);
              }
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      let errorMessage = "Unknown error occurred.";
      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          errorMessage = err.response.data.detail[0].msg.replace("Value error, ", "");
        } else {
          errorMessage = err.response.data.detail;
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      setMessages(prev => [...prev, { role: 'ai', content: `Sorry, I encountered an error: ${errorMessage}` }]);
    } finally {
      setLoading(false);
    }
  };

  const toggleDocument = (docId) => {
    setActiveDocuments(prev => {
      if (prev.includes(docId)) {
        return prev.filter(id => id !== docId);
      } else {
        if (prev.length >= 5) {
          alert("You can only compare up to 5 documents at once.");
          return prev;
        }
        return [...prev, docId];
      }
    });
  };

  const activeDocObjs = documents.filter(d => activeDocuments.includes(d.document_id));
  const activeDocTitle = activeDocObjs.length > 0 ? activeDocObjs.map(d => d.title).join(", ") : "No documents selected";
  const headerPrefix = activeDocObjs.length > 1 ? "Currently Comparing:" : "Currently Analyzing:";

  return (
    <div className="app-container animate-fade-in">
      <Sidebar 
        user={user}
        logout={logout}
        sessions={sessions}
        documents={documents}
        activeDocuments={activeDocuments}
        activeSession={activeSession}
        setActiveSession={setActiveSession}
        setMessages={setMessages}
        loadSession={loadSession}
        toggleDocument={toggleDocument}
        fileInputRef={fileInputRef}
        handleFileUpload={handleFileUpload}
      />

      <div className="main-content">
        {activeDocObjs.length > 0 && (
          <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--surface-border)', background: 'rgba(255,255,255,0.02)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{headerPrefix}</span>
            <span style={{ fontWeight: 600, color: 'var(--primary-light)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{activeDocTitle}</span>
          </div>
        )}
        
        <ChatWindow 
          messages={messages} 
          loading={loading} 
          messagesEndRef={messagesEndRef} 
        />

        <ChatInput 
          input={input}
          setInput={setInput}
          loading={loading}
          uploading={uploading}
          ingestingUrl={ingestingUrl}
          sendMessage={sendMessage}
          showMenu={showMenu}
          setShowMenu={setShowMenu}
          handleUrlIngest={handleUrlIngest}
          fileInputRef={fileInputRef}
          menuRef={menuRef}
        />
      </div>
    </div>
  );
};

export default Dashboard;
