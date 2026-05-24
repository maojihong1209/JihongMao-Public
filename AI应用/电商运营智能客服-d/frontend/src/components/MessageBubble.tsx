import { AIResponse } from '../types';

interface Props {
  role: 'user' | 'agent';
  content: string;
  aiType?: AIResponse['type'];
  complaintLevel?: string;
  complaintType?: string;
}

const LEVEL_STYLES: Record<string, string> = {
  '高': 'bg-red-100 text-red-700 border-red-200',
  '中': 'bg-orange-100 text-orange-700 border-orange-200',
  '低': 'bg-yellow-100 text-yellow-700 border-yellow-200',
};

const LEVEL_LABELS: Record<string, string> = {
  '高': '高优先级',
  '中': '已关注',
  '低': '已记录',
};

const TYPE_LABELS: Record<string, string> = {
  '物流': '物流问题',
  '质量': '质量问题',
  '服务态度': '服务态度',
  '其他': '其他反馈',
};

export const MessageBubble = ({ role, content, aiType, complaintLevel, complaintType }: Props) => {
  const isUser = role === 'user';

  return (
    <div className={`flex gap-2.5 mb-5 ${isUser ? 'flex-row-reverse' : 'flex-row'} animate-message-in`}>
      {/* 头像 */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm
        ${isUser
          ? 'bg-gradient-to-br from-brand-400 to-brand-500 text-white shadow-sm'
          : 'bg-gradient-to-br from-emerald-400 to-emerald-500 text-white shadow-sm'
        }`}
      >
        {isUser ? '我' : '鸿'}
      </div>

      {/* 气泡 */}
      <div className={`max-w-[75%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-gradient-to-br from-brand-500 to-brand-600 text-white rounded-2xl rounded-tr-md shadow-sm shadow-brand-200'
            : 'bg-white border border-gray-200 text-gray-800 rounded-2xl rounded-tl-md shadow-sm'
        }`}>
          {aiType === 'order_card' ? (
            <div className="font-mono text-xs space-y-1 bg-gray-50 rounded-xl p-3 border border-gray-200">
              {content.split('\n').map((line, i) => (
                <div key={i} className={i === 0 ? 'font-semibold text-sm text-gray-900 mb-1' : 'text-gray-700'}>{line}</div>
              ))}
            </div>
          ) : aiType === 'human_tip' ? (
            <div>
              {(complaintLevel || complaintType) && (
                <div className="flex items-center gap-2 mb-2">
                  {complaintLevel && (
                    <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-medium border ${LEVEL_STYLES[complaintLevel] || LEVEL_STYLES['中']}`}>
                      {LEVEL_LABELS[complaintLevel] || complaintLevel}
                    </span>
                  )}
                  {complaintType && (
                    <span className="inline-block px-2 py-0.5 rounded-md text-xs text-gray-600 bg-gray-100 border border-gray-200">
                      {TYPE_LABELS[complaintType] || complaintType}
                    </span>
                  )}
                  {complaintLevel === '高' && (
                    <span className="inline-block px-2 py-0.5 rounded-md text-xs text-red-700 bg-red-50 border border-red-200 animate-pulse">
                      已优先转接
                    </span>
                  )}
                </div>
              )}
              <p className="text-gray-800">{content}</p>
              {content.includes('人工客服') && (
                <a href="https://www.xxx.com/人工客服" target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1.5 mt-3 text-white bg-gradient-to-r from-brand-500 to-brand-600 px-4 py-2 rounded-full text-sm font-medium hover:from-brand-600 hover:to-brand-700 transition-all shadow-sm"
                >
                  <span>👩‍💼</span> 联系人工客服
                </a>
              )}
            </div>
          ) : aiType === 'comparison_card' ? (
            <div>
              <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-100">
                <span className="text-base">📊</span>
                <span className="text-sm font-semibold text-gray-700">商品对比</span>
              </div>
              <div className="text-gray-800 text-sm leading-relaxed whitespace-pre-wrap">{content}</div>
            </div>
          ) : !content ? (
            <div className="flex items-center gap-1 py-1">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          ) : (
            <p>{content}</p>
          )}
        </div>
      </div>
    </div>
  );
};
