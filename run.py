import os
import sys
import uvicorn

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    print("==========================================================")
    print(">> Starting CareerShield ML: Gmail Cyber Filter & ML Lab")
    print(f">> Application running at: http://localhost:{port}")
    print("==========================================================")
    uvicorn.run("api.main:app", host="127.0.0.1", port=port, reload=True)
