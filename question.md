项目重新启动后数量发生变化，应该是数据库同步有问题
对话栏自动上拉
分镜图review
set -a; source .env; set +a; ./.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000