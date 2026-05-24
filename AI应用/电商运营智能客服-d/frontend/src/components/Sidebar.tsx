import { useState } from 'react';
import { Session } from '../types';
import { renameSession, deleteSession } from '../api';

interface Props {
  sessions: Session[];
  activeId: string;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  username?: string;
  onLogout: () => void;
}

export const Sidebar = ({ sessions, activeId, onNewChat, onSelect, onRename, onDelete, username, onLogout }: Props) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const handleDoubleClick = (s: Session) => {
    setEditingId(s.id);
    setEditTitle(s.title);
  };

  const handleBlur = () => {
    if (editingId && editTitle.trim()) {
      renameSession(editingId, editTitle.trim());
      onRename(editingId, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleBlur();
    if (e.key === 'Escape') setEditingId(null);
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm('确定要删除这个对话吗？')) return;
    await deleteSession(id);
    onDelete(id);
  };

  return (
    <aside className="w-64 flex flex-col bg-white border-r border-gray-100">
      {/* 头部 */}
      <div className="px-5 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center text-white text-sm font-bold shadow-sm">
            鸿
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-800 leading-tight">鸿途客服</h1>
            <p className="text-xs text-gray-500">{username}</p>
          </div>
        </div>
        <button onClick={onNewChat}
          className="w-full flex items-center justify-center gap-1.5 bg-gradient-to-r from-brand-500 to-brand-600 text-white py-2 rounded-lg text-xs font-medium
                     hover:from-brand-600 hover:to-brand-700 active:scale-[0.98] transition-all shadow-sm"
        >
          <span className="text-base leading-none">+</span> 新对话
        </button>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
        {sessions.length === 0 && (
          <p className="text-center text-xs text-gray-400 mt-8">暂无对话记录</p>
        )}
        {sessions.map(s => (
          <div key={s.id}
            onClick={() => onSelect(s.id)}
            onDoubleClick={() => handleDoubleClick(s)}
            className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all duration-150
              ${s.id === activeId
                ? 'bg-brand-50 text-brand-700 shadow-sm font-medium'
                : 'text-gray-700 hover:bg-gray-50'
              }`}
          >
            {/* 对话图标 */}
            <span className="text-xs flex-shrink-0 opacity-50">💬</span>

            <div className="flex-1 min-w-0">
              {editingId === s.id ? (
                <input
                  autoFocus
                  value={editTitle}
                  onChange={e => setEditTitle(e.target.value)}
                  onBlur={handleBlur}
                  onKeyDown={handleKeyDown}
                  onClick={e => e.stopPropagation()}
                  className="w-full border border-brand-300 rounded px-1.5 py-0.5 text-xs outline-none bg-white"
                />
              ) : (
                <span className="truncate block text-xs" title="双击修改名称">{s.title}</span>
              )}
            </div>

            {/* 删除按钮 */}
            <button
              onClick={e => handleDelete(e, s.id)}
              className="flex-shrink-0 opacity-0 group-hover:opacity-60 hover:!opacity-100 text-gray-400 hover:text-red-500 text-sm leading-none px-0.5 transition-all"
              title="删除"
            >
              &times;
            </button>
          </div>
        ))}
      </div>

      {/* 底部 */}
      <div className="px-5 py-3 border-t border-gray-100">
        <button onClick={onLogout}
          className="flex items-center gap-2 text-xs text-gray-500 hover:text-red-500 transition-colors"
        >
          <span>🚪</span> 退出登录
        </button>
      </div>
    </aside>
  );
};
