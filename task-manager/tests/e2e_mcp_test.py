import subprocess
import json
import os
import sys

def run_test():
    server_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp_server.py")
    
    env = os.environ.copy()
    # We will test against the same dev DB that the FastApi uses
    
    # Start the subprocess
    process = subprocess.Popen(
        [sys.executable, server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "projects_list"}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "groups_list", "arguments": {"project_id": 1}}}
    ]
    
    print("Testing MCP JSON-RPC Server...")
    for req in requests:
        req_str = json.dumps(req)
        print(f"-> {req_str}")
        process.stdin.write(req_str + "\n")
        process.stdin.flush()
        
        res_str = process.stdout.readline().strip()
        print(f"<- {res_str}")
        
        res = json.loads(res_str)
        assert res.get("jsonrpc") == "2.0"
        assert res.get("id") == req["id"]
        if "error" in res:
            print(f"ERROR returned: {res['error']}")
            
        print("-" * 40)
        
    process.terminate()
    print("E2E Validation tests successfully ran!")

if __name__ == "__main__":
    run_test()
