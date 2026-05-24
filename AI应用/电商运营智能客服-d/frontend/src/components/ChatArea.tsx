import { useState, useEffect, useRef } from 'react';
import { getHistory, sendMessageStream } from '../api';
import { HistoryMessage } from '../types';
import { MessageBubble } from './MessageBubble';

interface Props {
  sessionId: string;
  onTitleChange: (title: string) => void;
}

const WELCOME_SUGGESTIONS = [
  '你好，介绍下自己',
  '我想找一件适合夏天穿的T恤',
  '帮我查一下我的订单',
];

export const ChatArea = ({ sessionId, onTitleChange }: Props) => {
  const [messages, setMessages] = useState<HistoryMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await getHistory(sessionId);
        setMessages(res.data.messages);
      } catch { setMessages([]); }
    })();
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg = text.trim();
    setInput('');
    const userMessage: HistoryMessage = { role: 'user', content: userMsg };
    const placeholder: HistoryMessage = { role: 'agent', content: '' };
    setMessages(prev => [...prev, userMessage, placeholder]);
    setLoading(true);

    let isFirst = messages.length === 0;

    sendMessageStream(
      userMsg,
      sessionId,
      (token) => {
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === 'agent') {
            updated[updated.length - 1] = { ...last, content: last.content + token };
          }
          return updated;
        });
      },
      (intent, aiResponse) => {
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === 'agent') {
            updated[updated.length - 1] = {
              ...last,
              content: aiResponse.content,
              type: aiResponse.type,
              complaintLevel: (aiResponse as any).complaint_level,
              complaintType: (aiResponse as any).complaint_type,
            } as any;
          }
          return updated;
        });
        if (isFirst) {
          const title = aiResponse.content.slice(0, 20) + (aiResponse.content.length > 20 ? '…' : '');
          onTitleChange(title || '新对话');
        }
        setLoading(false);
      },
      (err) => {
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === 'agent' && !last.content) {
            updated[updated.length - 1] = { ...last, content: '抱歉，出错了，请重试' };
          }
          return updated;
        });
        setLoading(false);
      },
    );
  };

  const handleSend = () => send(input);

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-gray-50 to-white">
      {/* 消息区 */}
      <div className="flex-1 overflow-y-auto px-4 pt-4">
        {messages.length === 0 ? (
          /* 欢迎页 */
          <div className="flex flex-col items-center justify-center h-full animate-fade-in">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-brand-200 mb-4">
              鸿
            </div>
            <h2 className="text-lg font-semibold text-gray-700 mb-1">你好，我是小鸿</h2>
            <p className="text-sm text-gray-500 mb-8">你的智能电商客服助手，有什么可以帮你？</p>
            <div className="flex flex-wrap justify-center gap-2 max-w-sm">
              {WELCOME_SUGGESTIONS.map((s, i) => (
                <button key={i} onClick={() => send(s)}
                  className="px-4 py-2 rounded-full border border-gray-300 bg-white text-sm text-gray-700
                             hover:border-brand-400 hover:text-brand-600 hover:bg-brand-50 hover:shadow-md transition-all shadow-sm"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <MessageBubble
              key={idx}
              role={msg.role}
              content={msg.content}
              aiType={(msg as any).type}
              complaintLevel={(msg as any).complaintLevel}
              complaintType={(msg as any).complaintType}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="px-4 pb-4 pt-2">
        <div className="max-w-3xl mx-auto flex items-center gap-2 bg-white rounded-2xl border border-gray-200 px-4 py-2 shadow-sm
                        focus-within:border-brand-300 focus-within:ring-4 focus-within:ring-brand-50 transition-all">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="输入您的问题..."
            disabled={loading}
            className="flex-1 py-1.5 text-sm bg-transparent outline-none placeholder-gray-400 disabled:opacity-40"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="flex-shrink-0 w-9 h-9 rounded-full bg-gradient-to-br from-brand-500 to-brand-600 text-white flex items-center justify-center
                       hover:from-brand-600 hover:to-brand-700 disabled:opacity-30 disabled:cursor-not-allowed active:scale-95 transition-all"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
        <p className="text-center text-xs text-gray-400 mt-2">
          鸿途客服可能会产生不准确回复，请核对关键信息
        </p>
      </div>
    </div>
  );
};
