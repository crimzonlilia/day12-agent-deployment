# Deployment Information - My Production Agent

## 🚀 Public URL
**URL**: [https://agent-production-06af.up.railway.app](https://agent-production-06af.up.railway.app)

## 🛠 Platform & Architecture
- **Platform**: Railway.app
- **Architecture**: 
    - **Web Service**: FastAPI Agent (State-of-the-art production structure)
    - **Database**: Redis (State store for Conversation History & Rate Limiting)
- **Monitoring**: Structured JSON Logging configured.

## 🔒 Security
- **Authentication**: API Key required in header `X-API-Key`.
- **Hành động**: `X-API-Key: tksgssk`

## 🧪 Test Commands

### 1. Health Check
```bash
curl https://agent-production-06af.up.railway.app/health
# Expected: {"status": "ok", "version": "1.0.0", ...}
```

### 2. Readiness Check
```bash
curl https://agent-production-06af.up.railway.app/ready
# Expected: {"ready": true, "redis": "ok"}
```

### 3. Ask a Question (Hỏi Agent)
```bash
curl https://agent-production-06af.up.railway.app/ask \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tksgssk" \
  -d '{"question": "How to deploy AI Agent to Railway?", "stream": false}'
```

### 4. Test Rate Limiting
(Chạy lệnh này liên tục 11 lần trong 1 phút để thấy lỗi 429)
```bash
curl https://agent-production-06af.up.railway.app/ask \
  -X POST \
  -H "X-API-Key: tksgssk" \
  -H "Content-Type: application/json" \
  -d '{"question": "spam"}'
```

## 📈 Maintenance
- **Logs**: `railway logs --service agent`
- **Scale up**: `railway up --service agent`