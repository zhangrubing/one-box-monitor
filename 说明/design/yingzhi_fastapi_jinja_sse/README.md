# 英智AI监控系统 · 方案B（SSE 完整页面）

- 登录：`/login`（默认 admin / admin123）
- 登录后所有页面右上角都有 **退出** 按钮
- 仪表盘：首屏从 `/api/metrics/system` 拉数据，随后通过 `/events/metrics`（SSE）每 2 秒更新 CPU/GPU
- 页面清单：仪表盘/硬件/GPU/网络/存储/日志/告警/运维/设置/报表/用户/审计/关于

## 运行
```bash
./run.sh
# 打开 http://127.0.0.1:8000/login
```
