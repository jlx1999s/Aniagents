# Manju Platform

## 后端启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

默认前端请求 `http://localhost:8000`。如果后端地址不同，设置环境变量：

```bash
cd frontend
echo "VITE_API_BASE=http://127.0.0.1:8000" > .env.local
```

## 联调流程

1. 启动后端
2. 启动前端
3. 打开 `http://localhost:5173`
4. 前端自动创建项目并通过 SSE 订阅实时状态
5. 在右侧面板使用 `Approve / Revise / Reject` 驱动人工审核回路

## 接入 VectorEngine API（配置 Key）

1. 在项目根目录创建后端环境变量文件：

```bash
cp .env.example .env
```

2. 编辑 `.env`，填入：

```bash
VECTORENGINE_API_KEY=你的真实Token
VECTORENGINE_BASE_URL=https://api.vectorengine.ai
```

3. 启动后端时加载环境变量：

```bash
source .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. 前端进入「设置」页，把对应阶段的 Provider 切到 `VectorEngine`，并设置模型名（例如 `gemini-2.5-pro`）。

密钥只在后端环境变量读取，不在前端存储。
