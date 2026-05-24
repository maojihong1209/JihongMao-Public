import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { loginUser, registerUser } from '../api';
import { useAuth } from '../hooks/useAuth';

export const AuthPage = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username || !password) { setError('请输入用户名和密码'); return; }
    try {
      const res = isRegister
        ? await registerUser({ username, password })
        : await loginUser(username, password);
      login(res.data.access_token);
      navigate('/chat');
    } catch (err: any) {
      setError(err.response?.data?.detail || '操作失败');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 via-white to-indigo-50">
      {/* 背景装饰 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-brand-200/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-200/15 rounded-full blur-3xl" />
      </div>

      <form onSubmit={handleSubmit}
        className="relative bg-white p-8 rounded-2xl shadow-xl shadow-brand-100/40 border border-gray-100 w-[380px] space-y-5 animate-fade-in"
      >
        <div className="text-center space-y-1">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-brand-500 to-indigo-600 text-white text-xl font-bold shadow-md">
            鸿
          </div>
          <h2 className="text-xl font-semibold text-gray-800 mt-2">
            {isRegister ? '创建账号' : '欢迎回来'}
          </h2>
          <p className="text-sm text-gray-600">
            {isRegister ? '注册后即可使用智能客服' : '登录您的鸿途客服账号'}
          </p>
        </div>

        <div className="space-y-3">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <input
              type="text" placeholder="用户名" value={username}
              onChange={e => { setUsername(e.target.value); setError(''); }}
              className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 bg-gray-50/50 text-sm text-gray-800 placeholder-gray-500
                         focus:outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-50 focus:bg-white transition-all"
            />
          </div>
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <rect strokeLinecap="round" strokeLinejoin="round" x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 11V7a5 5 0 0110 0v4" />
            </svg>
            <input
              type="password" placeholder="密码" value={password}
              onChange={e => { setPassword(e.target.value); setError(''); }}
              className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 bg-gray-50/50 text-sm text-gray-800 placeholder-gray-500
                         focus:outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-50 focus:bg-white transition-all"
            />
          </div>
        </div>

        {error && (
          <div className="bg-red-50 text-red-600 text-xs px-4 py-2.5 rounded-lg border border-red-100 animate-fade-in">
            {error}
          </div>
        )}

        <button type="submit"
          className="w-full bg-gradient-to-r from-brand-500 to-brand-600 text-white py-2.5 rounded-xl text-sm font-medium
                     hover:from-brand-600 hover:to-brand-700 active:scale-[0.98] transition-all shadow-md shadow-brand-200/50"
        >
          {isRegister ? '注 册' : '登 录'}
        </button>

        <p className="text-center text-sm text-gray-600">
          {isRegister ? '已有账号？' : '没有账号？'}
          <span onClick={() => { setIsRegister(!isRegister); setError(''); }}
            className="text-brand-600 cursor-pointer ml-1 font-semibold hover:text-brand-700 transition-colors"
          >
            {isRegister ? '去登录' : '去注册'}
          </span>
        </p>
      </form>
    </div>
  );
};
