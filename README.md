# JTerm

[English](#english) | [中文](#中文)

---

## English

**JTerm** is a lightweight command-line tool that connects your local terminal to a remote Jupyter Notebook's built-in terminal over HTTP/WebSocket.

### Prerequisites

Ensure you have Python 3 installed. Then, install the required dependencies:

```bash
pip install -r requirements.txt
```

### Build

JTerm uses `pyinstaller` to package the script into a single, standalone executable. Run the provided build script:

```bash
chmod +x build.sh
./build.sh
```

The executable will be generated at `./dist/jterm`. You can move it to a directory included in your system's `PATH` (e.g., `/usr/local/bin/`) for global access.

### Usage

Simply pass the Jupyter URL containing the access token:

```bash
jterm "http://localhost:8888/?token=your_token"
```

**Options:**

- `--insecure`: Disable SSL certificate verification.
- `--keep`: Do not delete the remote terminal upon exiting.
- `--ping-interval`: WebSocket ping interval in seconds (default: 15.0).

---

## 中文

**JTerm** 是一个轻量级的命令行工具，用于通过 HTTP/WebSocket 将本地终端直接连接到远程 Jupyter Notebook 的内置终端。

### 环境准备

请确保已安装 Python 3，然后安装必需的依赖包：

```bash
pip install -r requirements.txt
```

### 编译构建

JTerm 使用 `pyinstaller` 将脚本打包为独立的单文件可执行程序。只需运行构建脚本：

```bash
chmod +x build.sh
./build.sh
```

编译完成后，可执行文件将生成在 `./dist/jterm`。建议将其移动到系统的 `PATH` 目录（例如 `/usr/local/bin/`）以便全局调用。

### 使用方法

直接传入包含 token 的 Jupyter URL 即可连接：

```bash
jterm "http://localhost:8888/?token=your_token"
```

**可选参数：**

- `--insecure`: 禁用 SSL 证书验证。
- `--keep`: 退出时不要删除远程终端。
- `--ping-interval`: WebSocket ping 间隔时长，单位为秒（默认: 15.0）。
