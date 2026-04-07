@echo off
cd /d "C:\Users\itsva\Desktop\my_jarvis"
start http://localhost:8000
python server.py
```

**Step 2 — Drop it into Windows startup folder**

Press `Win + R`, type this exactly and hit Enter:
```
shell:startup