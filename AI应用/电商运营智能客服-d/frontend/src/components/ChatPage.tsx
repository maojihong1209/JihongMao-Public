import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../hooks/useAuth';
import { getMe, getSessions } from '../api';
import { UserInfo, Session } from '../types';
import { Sidebar } from './Sidebar';
import { ChatArea } from './ChatArea';

export const ChatPage = () => {
  const { logout } = useAuth();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');

  useEffect(() => {
    (async () => {
      try {
        const me = await getMe(); setUser(me.data);
        const sess = await getSessions();
        setSessions(sess.data);
        if (sess.data.length > 0) setActiveSessionId(sess.data[0].id);
      } catch { logout(); }
    })();
  }, []);

  const handleNewChat = () => {
    const newId = `${user!.id}_${user!.username}_${Date.now()}`;
    setSessions(prev => [{ id: newId, title: '新对话' }, ...prev]);
    setActiveSessionId(newId);
  };

  const handleTitleUpdate = useCallback((id: string, title: string) => {
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title } : s));
  }, []);

  const handleDelete = useCallback((id: string) => {
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id);
      if (activeSessionId === id && next.length > 0) setActiveSessionId(next[0].id);
      else if (activeSessionId === id) setActiveSessionId('');
      return next;
    });
  }, [activeSessionId]);

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar
        sessions={sessions}
        activeId={activeSessionId}
        onNewChat={handleNewChat}
        onSelect={setActiveSessionId}
        onRename={handleTitleUpdate}
        onDelete={handleDelete}
        username={user?.username}
        onLogout={logout}
      />
      <main className="flex-1 flex flex-col">
        {activeSessionId ? (
          <ChatArea sessionId={activeSessionId} onTitleChange={title => handleTitleUpdate(activeSessionId, title)} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400">点击左侧「新对话」开始</div>
        )}
      </main>
    </div>
  );
};