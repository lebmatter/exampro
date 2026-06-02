# ExamPro Load Testing with Locust

This directory contains comprehensive load testing tools for the ExamPro exam management system using Locust.

## 📁 Files Structure

```
locust/
├── requirements.txt          # Python dependencies
├── data.json                # Test configuration and sample data
├── frappe_client.py         # Frappe backend client wrapper
├── locustfile.py           # Main Locust load testing scenarios
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Test Settings

Edit `data.json` to match your environment:

```json
{
  "frappe_config": {
    "site_url": "http://localhost:8000",
    "admin_username": "Administrator", 
    "admin_password": "your_admin_password"
  },
  "test_config": {
    "num_candidates": 50,
    "num_exams": 3,
    "questions_per_exam": 15,
    "concurrent_users": 10,
    "spawn_rate": 2
  }
}
```

### 3. Setup Test Data

```bash
python test_data_manager.py setup
```

This creates:
- Test user accounts
- Question categories and questions
- Sample exams
- Exam schedules
- User registrations

### 4. Run Load Test

```bash
mkdir -p results

# Smoke (50 users, 10 min)
locust -f locustfile.py --host=https://exam.example.com \
       --users=50  --spawn-rate=10 --run-time=10m --headless \
       --csv=results/50u --html=results/50u.html

# Mid load (100 users, 15 min)
locust -f locustfile.py --host=https://exam.example.com \
       --users=100 --spawn-rate=10 --run-time=15m --headless \
       --csv=results/100u --html=results/100u.html

# Target load (500 users, 25 min)
locust -f locustfile.py --host=https://exam.example.com \
       --users=500 --spawn-rate=20 --run-time=25m --headless \
       --csv=results/500u --html=results/500u.html
```

Each Locust user is mapped deterministically to one seeded candidate
(`loaduser{0..N-1}_{session_id}`), so `--users` must be ≤ `num_candidates`
in `data.json`. The default seed is **500** candidates.

The harness drives three independent per-user loops at production cadence:
- Answer: `get_question` → "thinking" sleep → `submit_question_response`, every 25–60 s
- Tracking: `post_tracking_info`, every 15 s (proctored exams only)
- Video: `get_video_upload_url` → direct `POST` to S3/R2 with ~80 KB random bytes, every 10 s (proctored exams only)

Video bytes are fake `os.urandom(80*1024)` — the S3 policy only enforces
`Content-Type: video/webm` and a 1 B–10 MB size range, so random bytes are
indistinguishable from a real webm for load-test purposes.

### 5. Cleanup Test Data

```bash
# Cleanup latest test session
python test_data_manager.py cleanup

# Cleanup specific session
python test_data_manager.py cleanup loadtest_20250820_143052_abc123

# List all sessions
python test_data_manager.py list
```

## 📊 Load Testing Scenarios

### Primary User Types

1. **ExamTakerUser** (Weight: 10) - Main load
   - Login and view my exams
   - Start and complete exams
   - Answer questions with realistic timing
   - Submit exams and view results

2. **ExamCreatorUser** (Weight: 1) - Administrative load
   - Manage exams and questions
   - View submissions and analytics

3. **ProctorUser** (Weight: 1) - Monitoring load
   - Monitor ongoing exams
   - Check flagged sessions

### Test Scenarios Covered

#### 🎯 Complete Exam Flow
- User login with test credentials
- Navigate to "My Exams" page
- View exam details
- Start exam (creates submission)
- Retrieve exam questions
- Answer questions with realistic delays
- Submit completed exam
- View results

#### 📈 Performance Metrics
- Response times for each endpoint
- Concurrent user handling
- Database performance under load
- Memory and CPU usage patterns

#### 🔍 Edge Cases
- Session timeouts during exams
- Rapid question submissions
- Concurrent exam submissions
- Large result set pagination

## 🛠️ Configuration Options

### Test Data Configuration

```json
{
  "test_config": {
    "num_candidates": 50,        // Number of test users to create
    "num_exams": 3,             // Number of test exams
    "questions_per_exam": 15,   // Questions per exam
    "exam_duration_minutes": 30, // Exam time limit
    "concurrent_users": 10,     // Peak concurrent users
    "spawn_rate": 2            // Users spawned per second
  }
}
```

### Load Test Parameters

```bash
# Test duration and intensity
--users=50              # Peak number of concurrent users
--spawn-rate=5          # Users spawned per second
--run-time=30m          # Total test duration

# Test modes
--headless              # Run without web UI
--csv=results           # Export results to CSV
--html=report.html      # Generate HTML report
```

## 📋 Test Data Management

### Creating Test Data

The `test_data_manager.py` script creates a complete test environment:

```python
# Creates:
# - 50 test user accounts (teststudent0_session@loadtest.example.com)
# - Question categories and pools
# - Multiple exam templates
# - Scheduled exams with registrations
```

### Session Management

Each test run creates a unique session with timestamped data:

```
test_session_loadtest_20250820_143052_abc123.json
```

This allows:
- Multiple concurrent test sessions
- Easy cleanup of specific sessions
- Data isolation between test runs

### Cleanup Strategies

```bash
# Quick cleanup (latest session)
python test_data_manager.py cleanup

# Targeted cleanup
python test_data_manager.py cleanup session_id

# Bulk cleanup (all sessions)
for session in $(python test_data_manager.py list | grep -o 'loadtest_[^"]*'); do
    python test_data_manager.py cleanup $session
done
```

## 🎛️ Monitoring and Metrics

### Key Performance Indicators

1. **Response Times**
   - Login: < 1s
   - Page loads: < 2s 
   - Exam start: < 3s
   - Question submission: < 1s
   - Exam submission: < 5s

2. **Throughput**
   - Concurrent exam takers
   - Questions answered per minute
   - Exam submissions per hour

3. **Error Rates**
   - Failed logins
   - Timeout errors
   - Database connection issues

### Locust Web Interface

Access at `http://localhost:8089` for real-time monitoring:

- Live performance graphs
- Request statistics
- Error tracking
- User simulation controls

### Custom Metrics

```python
# Track custom events
events.request.add_listener
def on_request(request_type, name, response_time, response_length, 
               response, context, exception, **kwargs):
    if response_time > 5000:
        logger.warning(f"Slow request: {name} took {response_time}ms")
```

## 🚨 Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   # Check if Frappe site is running
   curl http://localhost:8000/api/method/ping
   ```

2. **Authentication Failures**
   ```bash
   # Verify admin credentials in data.json
   # Check Frappe user permissions
   ```

3. **No Test Data**
   ```bash
   # Ensure test data setup completed successfully
   python test_data_manager.py list
   ```

4. **Database Locks**
   ```bash
   # Reduce concurrent users or spawn rate
   locust --users=10 --spawn-rate=1
   ```

### Debug Mode

```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Track all requests
events.request.add_listener(log_all_requests)
```

### Performance Tuning

```bash
# Optimize for high load
ulimit -n 65536                    # Increase file descriptors
locust --users=1000 --spawn-rate=10 # Gradual ramp-up
```

## 📚 Advanced Usage

### Custom Test Scenarios

```python
class CustomExamUser(HttpUser):
    @task(1)
    def custom_exam_flow(self):
        # Your custom test logic
        pass
```

### Integration with CI/CD

```yaml
# Example GitHub Actions workflow
- name: Run Load Tests
  run: |
    python test_data_manager.py setup
    locust -f locustfile.py --host=${{ env.TEST_URL }} \
           --users=20 --spawn-rate=2 --run-time=5m --headless \
           --csv=results --html=report.html
    python test_data_manager.py cleanup
```

### Performance Baseline

```bash
# Establish baseline performance
locust -f locustfile.py --users=1 --spawn-rate=1 --run-time=5m \
       --csv=baseline --html=baseline.html
```

## 🔗 API Endpoints Tested

- `POST /api/method/login` - User authentication
- `GET /my-exams` - Exam listing page
- `GET /exam` - Exam details page
- `POST /api/method/exampro.exam_pro.api.examops.start_exam` - Start exam
- `GET /api/method/exampro.exam_pro.api.examops.get_questions` - Get questions
- `POST /api/method/exampro.exam_pro.api.examops.submit_answer` - Submit answers
- `POST /api/method/exampro.exam_pro.api.examops.submit_exam` - Submit exam
- `GET /exam/result` - View results
- `GET /leaderboard` - View leaderboard
- `GET /proctor` - Proctor monitoring
- `GET /evaluate` - Evaluation page

## 📞 Support

For issues with the load testing setup:

1. Check Frappe logs: `tail -f sites/your-site/logs/web.log`
2. Monitor system resources: `htop`, `iotop`
3. Review Locust logs for errors
4. Verify test data integrity with `test_data_manager.py list`

---

**Note**: Always run load tests in a dedicated test environment, never against production systems.
