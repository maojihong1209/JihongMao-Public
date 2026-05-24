import { useState, useEffect, useRef, DragEvent, useCallback } from 'react';
import { getKbFiles, getKbFileDetail, deleteKbFile, deleteKbChunk } from '../api';
import type { KbFile, KbChunk } from '../types';

const ALLOWED_EXTS = ['txt', 'pdf', 'csv', 'docx', 'md'];
const PAGE_SIZE = 10;

function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

export const KbUploadPage = () => {
  const [tab, setTab] = useState<'list' | 'upload'>('list');

  // ---- 文件列表状态 ----
  const [files, setFiles] = useState<KbFile[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [listLoading, setListLoading] = useState(false);
  const [expandedFile, setExpandedFile] = useState<number | null>(null);
  const [chunks, setChunks] = useState<KbChunk[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);

  // ---- 上传状态 ----
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<{ type: '' | 'loading' | 'success' | 'error'; msg: string }>({ type: '', msg: '' });
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // ---- 加载文件列表 ----
  const loadFiles = useCallback(async (p: number) => {
    setListLoading(true);
    try {
      const res = await getKbFiles(p, PAGE_SIZE);
      setFiles(res.data.items);
      setTotal(res.data.total);
      setPage(p);
    } catch {
      setFiles([]);
      setTotal(0);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'list') loadFiles(1);
  }, [tab, loadFiles]);

  // ---- 展开文件 chunks ----
  const toggleExpand = async (fileId: number) => {
    if (expandedFile === fileId) {
      setExpandedFile(null);
      setChunks([]);
      return;
    }
    setExpandedFile(fileId);
    setChunksLoading(true);
    try {
      const res = await getKbFileDetail(fileId);
      setChunks(res.data.chunks);
    } catch {
      setChunks([]);
    } finally {
      setChunksLoading(false);
    }
  };

  // ---- 删除文件 ----
  const handleDeleteFile = async (fileId: number, filename: string) => {
    if (!confirm(`确定删除文件「${filename}」及其全部文档片段？`)) return;
    try {
      await deleteKbFile(fileId);
      if (expandedFile === fileId) { setExpandedFile(null); setChunks([]); }
      loadFiles(page);
    } catch { alert('删除失败'); }
  };

  // ---- 删除单条 chunk ----
  const handleDeleteChunk = async (chunkId: string) => {
    if (!confirm('确定删除该文档片段？')) return;
    try {
      await deleteKbChunk(chunkId);
      setChunks(prev => prev.filter(c => c.id !== chunkId));
      loadFiles(page);
    } catch { alert('删除失败'); }
  };

  // ---- 上传相关 ----
  const selectFile = (f: File) => {
    const ext = f.name.split('.').pop()?.toLowerCase() || '';
    if (!ALLOWED_EXTS.includes(ext)) {
      setUploadStatus({ type: 'error', msg: `不支持 "${ext}" 格式，仅支持：${ALLOWED_EXTS.join(', ')}` });
      return;
    }
    setUploadFile(f);
    setUploadStatus({ type: '', msg: '' });
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    const form = new FormData();
    form.append('file', uploadFile);
    const token = localStorage.getItem('token') || '';

    setUploadStatus({ type: 'loading', msg: '上传中，正在解析并写入知识库...' });
    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      const data = await res.json();
      if (res.ok) {
        setUploadFile(null);
        setUploadStatus({ type: 'success', msg: `上传成功！${data.chunk_count || data.detail || ''}` });
        setTimeout(() => setTab('list'), 1000);
      } else {
        setUploadStatus({ type: 'error', msg: data.detail || '上传失败' });
      }
    } catch {
      setUploadStatus({ type: 'error', msg: '网络错误，请检查后端是否启动' });
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const statusColors: Record<string, string> = {
    success: 'bg-green-50 text-green-700 border-green-200',
    error: 'bg-red-50 text-red-600 border-red-100',
    loading: 'bg-amber-50 text-amber-700 border-amber-200',
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 via-white to-indigo-50">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-brand-200/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-200/15 rounded-full blur-3xl" />
      </div>

      <div className="relative bg-white p-8 rounded-2xl shadow-xl w-[640px] space-y-5">
        <div className="text-center space-y-1">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-brand-500 to-indigo-600 text-white text-xl font-bold shadow-md">
            库
          </div>
          <h2 className="text-xl font-semibold text-gray-800 mt-2">知识库管理</h2>
        </div>

        {/* Tab 切换 */}
        <div className="flex bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setTab('list')}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === 'list' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            文件列表
          </button>
          <button
            onClick={() => setTab('upload')}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === 'upload' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            上传文件
          </button>
        </div>

        {/* Tab 1: 文件列表 */}
        {tab === 'list' && (
          <div className="space-y-3">
            {listLoading ? (
              <p className="text-center text-sm text-gray-400 py-8">加载中...</p>
            ) : files.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <p className="text-3xl mb-2">📭</p>
                <p className="text-sm">知识库为空，请先上传文档</p>
              </div>
            ) : (
              <>
                <div className="border border-gray-200 rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-500 text-xs">
                      <tr>
                        <th className="text-left px-4 py-2.5">文件名</th>
                        <th className="text-right px-4 py-2.5 w-20">大小</th>
                        <th className="text-right px-4 py-2.5 w-16">片段</th>
                        <th className="text-right px-4 py-2.5 w-16">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {files.map((f) => (
                        <tr key={f.id} className="hover:bg-gray-50/50">
                          <td
                            className="px-4 py-2.5 cursor-pointer"
                            onClick={() => toggleExpand(f.id)}
                          >
                            <span className="text-gray-800">{f.filename}</span>
                            <span className="text-xs text-gray-400 ml-2">{f.created_at?.slice(0, 10)}</span>
                          </td>
                          <td className="px-4 py-2.5 text-right text-gray-500">{formatSize(f.file_size)}</td>
                          <td className="px-4 py-2.5 text-right text-gray-500">{f.chunk_count}</td>
                          <td className="px-4 py-2.5 text-right">
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDeleteFile(f.id, f.filename); }}
                              className="text-red-400 hover:text-red-600 text-sm"
                              title="删除文件"
                            >
                              删除
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* 展开行: chunk 预览 */}
                {expandedFile !== null && (
                  <div className="border border-brand-200 rounded-xl p-4 bg-brand-50/30 space-y-2 max-h-64 overflow-y-auto">
                    <h4 className="text-sm font-medium text-gray-700">文档片段</h4>
                    {chunksLoading ? (
                      <p className="text-xs text-gray-400">加载中...</p>
                    ) : chunks.length === 0 ? (
                      <p className="text-xs text-gray-400">无片段</p>
                    ) : (
                      chunks.map((c) => (
                        <div key={c.id} className="flex gap-2 items-start bg-white rounded-lg p-2.5 border border-gray-100">
                          <span className="text-xs text-gray-400 mt-0.5 shrink-0">#{c.chunk_index + 1}</span>
                          <p className="text-xs text-gray-700 flex-1 line-clamp-3">{c.content.slice(0, 200)}</p>
                          <button
                            onClick={() => handleDeleteChunk(c.id)}
                            className="text-red-400 hover:text-red-600 text-xs shrink-0"
                          >
                            删除
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* 分页 */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-3 text-sm">
                    <button
                      onClick={() => loadFiles(page - 1)}
                      disabled={page <= 1}
                      className="px-3 py-1 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      上一页
                    </button>
                    <span className="text-gray-500">{page} / {totalPages}</span>
                    <button
                      onClick={() => loadFiles(page + 1)}
                      disabled={page >= totalPages}
                      className="px-3 py-1 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      下一页
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Tab 2: 上传 */}
        {tab === 'upload' && (
          <div className="space-y-5">
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
                ${dragOver ? 'border-brand-400 bg-brand-50/50' : 'border-gray-200 hover:border-brand-300 hover:bg-gray-50/50'}`}
            >
              <div className="text-4xl mb-3">📁</div>
              <p className="text-sm text-gray-600">点击上传或拖拽文件到此处</p>
              <p className="text-xs text-gray-400 mt-2">支持：{ALLOWED_EXTS.join(' / ')}</p>
            </div>
            <input ref={inputRef} type="file" accept={ALLOWED_EXTS.map(e => '.' + e).join(',')} className="hidden"
              onChange={e => e.target.files?.[0] && selectFile(e.target.files[0])} />

            {uploadFile && (
              <div className="bg-blue-50 rounded-lg px-4 py-3 text-sm text-gray-700">
                已选择：{uploadFile.name}（{formatSize(uploadFile.size)}）
              </div>
            )}

            {uploadStatus.type && (
              <div className={`rounded-lg px-4 py-3 text-sm border ${statusColors[uploadStatus.type] || ''}`}>
                {uploadStatus.msg}
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!uploadFile}
              className="w-full bg-gradient-to-r from-brand-500 to-brand-600 text-white py-2.5 rounded-xl text-sm font-medium
                         hover:from-brand-600 hover:to-brand-700 active:scale-[0.98] transition-all shadow-md shadow-brand-200/50
                         disabled:opacity-40 disabled:cursor-not-allowed"
            >
              上传到知识库
            </button>

            <div className="bg-gray-50 rounded-lg px-4 py-3 text-xs text-gray-500 leading-relaxed">
              <span className="font-medium text-gray-600">提示：</span><br />
              TXT/MD 直接解析 · PDF/DOCX 提取文字 · CSV 按行解析<br />
              上传后自动向量化，可供客服检索
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
