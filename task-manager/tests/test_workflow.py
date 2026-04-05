import subprocess
import json
import time

def call_tool(process, name, arguments):
    req = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments
        }
    }
    process.stdin.write(json.dumps(req) + "\n")
    process.stdin.flush()
    while True:
        line = process.stdout.readline()
        if not line: return None
        res = json.loads(line)
        if res.get("id") == req["id"]:
            return res
    return None

def main():
    # Start the MCP server
    # We use python explicitly to avoid batch file issues in this test
    # Ensure TASK_MANAGER_DB is set correctly in the environment before running
    proc = subprocess.Popen(
        ["python", "mcp_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    try:
        # 1. Initialize
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n")
        proc.stdin.flush()
        proc.stdout.readline()

        # 2. Create Task (check it's pending)
        print("Testing: task_create...")
        res = call_tool(proc, "task_create", {"title": "Workflow Test Task", "group_id": 16}) # using group 16 'others'
        task_info = json.loads(res["result"]["content"][0]["text"])
        task_id = task_info["id"]
        status = task_info.get("status")
        print(f"Created Task {task_id}, status: {status}")
        assert status == "pending"

        # 3. Push to In-Progress
        print("Testing: tasks_push (pending -> in-progress)...")
        res = call_tool(proc, "tasks_push", {"id": task_id})
        print(res["result"]["content"][0]["text"])
        assert "in-progress" in res["result"]["content"][0]["text"]

        # 4. Block Task
        print("Testing: tasks_block (in-progress -> blocked)...")
        res = call_tool(proc, "tasks_block", {"id": task_id, "reason": "Wait for user confirmation"})
        print(res["result"]["content"][0]["text"])
        assert "blocked" in res["result"]["content"][0]["text"]

        # 5. Push Blocked to Pending
        print("Testing: tasks_push (blocked -> pending)...")
        res = call_tool(proc, "tasks_push", {"id": task_id})
        print(res["result"]["content"][0]["text"])
        assert "pending" in res["result"]["content"][0]["text"]

        # 6. Push Pending to In-Progress
        print("Testing: tasks_push (pending -> in-progress again)...")
        res = call_tool(proc, "tasks_push", {"id": task_id})
        print(res["result"]["content"][0]["text"])
        assert "in-progress" in res["result"]["content"][0]["text"]

        # 7. Push to Done
        print("Testing: tasks_push (in-progress -> done)...")
        res = call_tool(proc, "tasks_push", {"id": task_id})
        print(res["result"]["content"][0]["text"])
        assert "done" in res["result"]["content"][0]["text"]

        # 8. Attempt invalid push
        print("Testing: invalid push (done -> ?)...")
        res = call_tool(proc, "tasks_push", {"id": task_id})
        print(res["result"]["content"][0]["text"])
        assert "Error" in res["result"]["content"][0]["text"]

        print("\nALL WORKFLOW TESTS PASSED!")

    finally:
        proc.terminate()

if __name__ == "__main__":
    main()
