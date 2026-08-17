You are an expert software engineer and senior reverse engineer specializing in automating program analysis. 

### Context:
I am building an automated pipeline in Python 3 (CPython) that needs to programmatically control the Ghidra software analysis suite in the background. To achieve this, I am using the `ghidra_bridge` library (https://github.com) which acts as an RPC bridge between my local Python 3 environment and Ghidra's internal Java/Jython engine. 

### Goal:
I need a robust, production-ready Python 3 script that manages the full lifecycle of a headless Ghidra analysis session, connects via the bridge, and extracts specific cryptographic artifacts or key routines from a target binary (e.g., an executable or a DLL).

### Technical Requirements:
1. **Headless Lifecycle Management:** Use Python's `subprocess` module to spin up Ghidra's `analyzeHeadless` utility. The command must import a specified binary, execute the `ghidra_bridge_server.py` script as a `-postScript`, handle startup delays/timeouts, and clean up the temporary project (`-deleteProject`).
2. **Bridge Integration:** Establish a stable `ghidra_bridge.GhidraBridge` connection with a safe response timeout.
3. **Automated Analysis Logic (Ghidra API over Bridge):**
   - Access the `currentProgram` memory space via `currentProgram.getMemory()`.
   - Scan the binary's memory for a specific byte signature or a specific set of cryptographic constants (e.g., standard AES S-box patterns, common file headers, or a custom byte array like `[0xDE, 0xAD, 0xBE, 0xEF]`).
   - If a signature match is found, extract the next 16 or 32 contiguous bytes from that memory address to capture potential static keys or configuration blocks.
4. **Resiliency & Output:** Wrap the execution in clean `try/except` blocks so that Ghidra crashes or timeouts do not crash the host script. Return the results as a clean Python dictionary or JSON object containing the status, the discovery address, and the extracted bytes in hex format.

### Your Task:
Write a comprehensive, modular, and well-commented Python 3 script that implements this architecture. Avoid pseudo-code and provide a complete, working blueprint that I can drop directly into my automation framework. Use modern Python best practices.
