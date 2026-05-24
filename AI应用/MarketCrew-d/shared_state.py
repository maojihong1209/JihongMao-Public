"""后台线程与 Streamlit 主线程之间的共享状态。

独立模块不受 st.rerun() 影响：Python 模块只初始化一次，缓存在 sys.modules。
使用 queue.Queue 实现线程安全通信，无需手动加锁。
"""
# 标准库
import queue

# 后台线程 → 主线程：每完成一个 Task 就 put 一条
progress_queue = queue.Queue()

# 后台线程 → 主线程：线程结束时 put 最终结果
result_queue = queue.Queue()
