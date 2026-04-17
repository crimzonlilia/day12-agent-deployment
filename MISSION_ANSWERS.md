# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
## Part 1: Localhost vs Production

### Exercise 1.1: Các anti-patterns tìm được

1. Hardcode API key trong source code: Dễ bị lộ khi push lên GitHub, gây rủi ro bảo mật nghiêm trọng.

2. Hardcode database URL (chứa username và password): Lộ thông tin kết nối database, có thể bị truy cập trái phép.

3. Không sử dụng config management (environment variables): Không linh hoạt giữa môi trường development và production.

4. Bật DEBUG mode trong code: Làm lộ thông tin hệ thống và không phù hợp trong production.

5. Sử dụng `print()` thay vì hệ thống logging chuẩn: Không kiểm soát được log level, không hỗ trợ monitoring.

6. Log ra thông tin nhạy cảm (API key): Vi phạm nguyên tắc bảo mật, dễ bị khai thác.

7. Không có health check endpoint (`/health`): Platform không thể kiểm tra trạng thái service để restart khi cần.

8. Port bị hardcode (port=8000): Không tương thích với môi trường cloud (PORT được inject qua env).

9. Host set là `localhost`: Service không thể truy cập từ bên ngoài container.

10. Sử dụng `reload=True` trong uvicorn: Chỉ phù hợp development, gây instability trong production.

11. Không có graceful shutdown: Khi service bị kill, request đang xử lý có thể bị mất.

12. Không có kiểm soát tài nguyên (ví dụ: max tokens hardcode): Không linh hoạt và khó scale.
...

### Exercise 1.3: Comparison table
### Exercise 1.3: Comparison table

| Feature | Basic | Advanced | Tại sao quan trọng? |
|--------|------|----------|---------------------|
| Config | Hardcode | Env vars | Linh hoạt giữa các môi trường, tránh sửa code khi deploy |
| Health check | Không có | Có `/health` | Giúp platform kiểm tra service còn sống để restart khi cần |
| Logging | print() | JSON logging | Dễ debug, monitor và tích hợp hệ thống logging |
| Shutdown | Đột ngột | Graceful (lifespan) | Tránh mất request đang xử lý khi tắt service |


## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. Base image là gì?  
→ `python:3.11-slim`  
(được dùng cho cả builder và runtime stage)

2. Working directory là gì?  
→ `/app`  
(nơi chứa source code và là thư mục chính khi container chạy)

3. Tại sao COPY requirements.txt trước?  
→ Để tận dụng Docker cache.  
Nếu requirements không đổi thì Docker không cần cài lại dependencies, giúp build nhanh hơn.

4. CMD vs ENTRYPOINT khác nhau thế nào?  
→ CMD: lệnh mặc định, có thể bị override khi chạy container.  
→ ENTRYPOINT: lệnh cố định, luôn được chạy, khó override hơn.  

Dockerfile này dùng CMD để chạy uvicorn, cho phép thay đổi khi cần.

### Exercise 2.3: Image size comparison

- Develop: 424 MB
- Production: 56.6 MB
- Difference: ~87% smaller

Production image nhỏ hơn đáng kể nhờ sử dụng multi-stage build,
chỉ giữ lại runtime cần thiết và loại bỏ build dependencies.

### Exercise 2.4: Docker Compose stack

#### Services được start:
- agent: FastAPI AI agent xử lý request
- redis: cache cho session và rate limiting
- qdrant: vector database cho RAG
- nginx: reverse proxy và load balancer

#### Cách các service giao tiếp:

- Client gửi request → nginx (port 80)
- nginx forward request đến agent
- agent xử lý request và:
  - truy cập redis để lưu/cache dữ liệu
  - truy cập qdrant để truy vấn vector (RAG)
- agent trả response → nginx → client

#### Architecture diagram:

Client  
  ↓  
Nginx (Reverse Proxy / Load Balancer)  
  ↓  
Agent (FastAPI)  
  ↓         ↓  
Redis     Qdrant

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- URL: https://day12railwayntdl-production.up.railway.app
- Screenshot: [Link to screenshot in repo]

## Part 4: API Security

### Exercise 4.1-4.3: Test results
```
minh@THILINH-LAP MINGW64 /d/HUST/20252/vinvin/day12_ha-tang-cloud_va_deployment (main)
$ curl http://localhost:8000/ask -X POST \
     -H "Content-Type: application/json" \
     -d '{"question": "hello"}'
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```
```
minh@THILINH-LAP MINGW64 /d/HUST/20252/vinvin/day12_ha-tang-cloud_va_deployment/03-cloud-deployment/railway (main)
$ curl -X POST "http://localhost:8000/ask?question=Hello" \
  -H "X-API-Key: my-secret-key"
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}(venv) 
```

### Exercise 4.4: Cost guard implementation

Tôi đã triển khai Cost Guard sử dụng **Redis atomic operations**:
1.  **Tracking**: Sử dụng lệnh `INCRBYFLOAT` trong Redis với key `cost:<user_id>:<YYYY-MM>` để tích lũy chi phí theo tháng của từng user.
2.  **Calculation**: Chi phí được tính dựa trên token thực tế. Với GPT-4o-mini: $0.00015/1K input và $0.0006/1K output.
3.  **Enforcement**: Trước mỗi request, hệ thống kiểm tra chi phí tích lũy. Nếu vượt ngưỡng `MONTHLY_BUDGET_USD` (mặc định $10), server trả về lỗi `402 Payment Required`.
4.  **TTL**: Các bản ghi cost có TTL 35 ngày để tự động reset/dọn dẹp theo tháng.

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes

1.  **Health & Readiness**:
    - `/health`: Liveness probe, trả về 200 OK ngay khi process running.
    - `/ready`: Readiness probe, kiểm tra kết nối tới Redis. Nếu Redis sập, trả về 503 để Load Balancer không đẩy traffic vào.
2.  **Graceful Shutdown**:
    - **Nhiệm vụ**: Implement signal handler cho `SIGTERM`.
    - **Kết quả test**: Khi gửi request tốn thời gian và chạy `kill -TERM`, server hiện thông báo "Graceful shutdown initiated", hoàn thành nốt request đang chạy rồi mới kết thúc. Request không bị drop đột ngột.
3.  **Stateless Design**: Di chuyển `conversation_history` từ memory (dict) sang **Redis (List/String)**. Điều này cho phép nhiều instances Agent cùng truy cập chung một bối cảnh của user.
4.  **Load Balancing**: Chạy Nginx làm Reverse Proxy, cấu hình `upstream` trỏ tới cluster agent. Test bằng `docker compose up --scale agent=3`. Kết quả log cho thấy các request được phân tán đều qua 3 instances khác nhau (Round Robin).

## Part 6: Final Project

### Architecture Summary
Hệ thống AI Agent hoàn chỉnh cho Production:
- **Security**: X-API-Key Auth + Redis Rate Limiter.
- **Scaling**: Stateless architecture + Nginx Load Balancer.
- **Reliability**: Health Checks + Graceful Shutdown + Redis Persistent State.
- **Deployment**: Multi-stage Docker build, deploy lên Cloud (Railway) thông qua Git/CLI.
