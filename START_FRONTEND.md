# 🚀 Quick Start Guide - Frontend

## Starting the Frontend Server

### Method 1: Direct Uvicorn (Recommended)
```bash
uvicorn frontend.app:create_app --host 0.0.0.0 --port 8000 --reload --factory
```

### Method 2: Using Startup Script
```bash
python frontend/startup.py
```

## 🎯 Access Points

Once running, you'll see:
```
🚀 Starting Multi-Agent Framework Frontend
📊 Dashboard: http://localhost:8000
🔧 API Docs: http://localhost:8000/docs
📡 WebSocket: ws://localhost:8000/ws
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 📋 Available Endpoints

- **Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **System Status**: http://localhost:8000/api/status
- **Agents List**: http://localhost:8000/api/agents
- **Task Creation**: POST http://localhost:8000/api/tasks

## 🎨 Features Available

### **Dashboard Features**
- **Real-time agent monitoring** with status indicators
- **Interactive task creation** with priority selection
- **Live execution logs** with color-coded messages
- **System overview** with agent, tool, and memory counts
- **Mobile-responsive** design

### **API Testing**
```bash
# Test system status
curl http://localhost:8000/api/status

# Test agents
curl http://localhost:8000/api/agents

# Create a test task
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"id": "test_001", "description": "Calculate fibonacci numbers", "priority": "high"}'
```

## 🔧 Troubleshooting

### **Port Already in Use**
```bash
# Use a different port
uvicorn frontend.app:create_app --port 8001 --factory
```

### **Import Errors**
```bash
# Ensure all dependencies are installed
pip install -r requirements.txt
```

### **Module Not Found**
```bash
# Run from project root
PYTHONPATH=. uvicorn frontend.app:create_app --factory
```

## 🌐 Browser Support

The frontend works on:
- **Chrome** (recommended)
- **Firefox**
- **Safari**
- **Edge**

## 📱 Mobile Access

The dashboard is fully responsive and works on:
- **Desktop** (full features)
- **Tablet** (optimized layout)
- **Mobile** (touch-friendly interface)

## 🎉 Success Indicators

When successfully running, you'll see:
- ✅ Dashboard at http://localhost:8000
- ✅ API docs at http://localhost:8000/docs
- ✅ Real-time updates every 5 seconds
- ✅ Task creation and execution
- ✅ Agent status monitoring