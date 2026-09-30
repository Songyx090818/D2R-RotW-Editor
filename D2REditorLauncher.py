# -*- coding: utf-8 -*-
"""
D2R RotW Editor - Created By 奈非天的侍从 启动器（pywebview 版）
  - 自动启动本地 HTTP 服务器（提供 index.html 与 base/ 数据）
  - 主体以 iframe 同源内嵌显示 index.html（编辑器界面，屏显信息栏已隐藏）
  - 关闭窗口即停止服务器

编译为 exe 后，exe 与 index.html / base/ 保持同目录即可运行。
依赖：pywebview（基于系统 WebView2 Runtime）。
"""
import os
import sys
import re
import json
import socket
import threading
import urllib.parse
import http.server
import socketserver

# ── 资源根目录：exe 运行时取 exe 所在目录；脚本运行时取脚本目录 ──
if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

PORT = 0
_server = None


# ── 本地静态服务器 ─────────────────────────────────────────────
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE, **kwargs)

    def do_GET(self):
        # 根路径返回启动器外壳页（屏显栏 + 内嵌编辑器 iframe）
        if self.path in ('/', '/shell', '/shell.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            body = SHELL_HTML.encode('utf-8')
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        # 保存存档到启动器所在目录下的 Save/（不存在则自动创建）
        try:
            if not self.path.startswith('/save'):
                self.send_response(404); self.end_headers(); return
            length = int(self.headers.get('Content-Length', 0) or 0)
            data = self.rfile.read(length) if length > 0 else b''
            qs = urllib.parse.urlparse(self.path).query
            name = (urllib.parse.parse_qs(qs).get('name') or [''])[0] or 'character.d2s'
            # 仅保留安全文件名，防止路径穿越
            safe = os.path.basename(name)
            safe = re.sub(r'[^A-Za-z0-9_.\-\u4e00-\u9fff]', '_', safe)
            # 前端已保证正确后缀（.d2s / .d2i）；仅当文件完全无扩展名时补默认 .d2s，不再强制改后缀
            if not os.path.splitext(safe)[1]:
                safe += '.d2s'
            save_dir = os.path.join(BASE, 'Save')
            os.makedirs(save_dir, exist_ok=True)
            dest = os.path.join(save_dir, safe)
            with open(dest, 'wb') as f:
                f.write(data)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': True, 'path': dest.replace(BASE + os.sep, '')}).encode('utf-8'))
        except Exception as e:
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'ok': False, 'error': str(e)}).encode('utf-8'))
            except Exception:
                pass

    def end_headers(self):
        # 禁用缓存，保证每次启动都读取最新 index.html / base/ 数据
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *args):  # 静默日志
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_server():
    global PORT, _server
    PORT = _free_port()
    _server = Server(('127.0.0.1', PORT), Handler)
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    return PORT


def stop_server():
    global _server
    if _server is not None:
        try:
            _server.shutdown()
            _server.server_close()
        except Exception:
            pass


# ── 屏显信息栏（4 行，第 4 行为作者）──
def _build_shell_html():
    base_esc = BASE.replace('&', '&amp;').replace('<', '&lt;')
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>D2R RotW Editor - Created By 奈非天的侍从</title>
<style>
  html, body { margin:0; height:100%; background:#0d0d0d; overflow:hidden; }
  #banner { display:none; }
  #wrap { height:100%; }
  iframe { width:100%; height:100%; border:0; display:block; background:#000; }
</style>
</head>
<body>
  <div id="banner">
    <div class="l1">暗黑破坏神 II：重制版 官方离线存档编辑器</div>
    <div class="l2">访问地址：http://127.0.0.1:%PORT%/Editor_v2.0.1.html</div>
    <div class="l3">请保持本窗口开启；关闭本窗口即停止服务</div>
    <div class="l4">作者：凯恩论坛 - 奈非天的侍从</div>
  </div>
  <div id="wrap"><iframe src="/Editor_v2.0.1.html" allow="fullscreen; autoplay"></iframe></div>
</body>
</html>
""".replace('%BASE%', base_esc).replace('%PORT%', str(PORT))


SHELL_HTML = ''


def main():
    global SHELL_HTML
    try:
        start_server()
    except Exception as e:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, "无法启动本地服务器：" + str(e) + "\n\n请检查 index.html 与 Data/ 文件夹是否与本程序同目录。",
            "D2R RotW Editor - Created By 奈非天的侍从", 0x10)
        return

    SHELL_HTML = _build_shell_html()
    url = "http://127.0.0.1:%d/" % PORT

    import webview
    try:
        window = webview.create_window(
            "D2R RotW Editor - Created By 奈非天的侍从",
            url,
            width=1320,
            height=900,
            resizable=True,
            min_size=(900, 640),
            background_color="#141414",
        )
        webview.start()
    except Exception as e:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, "无法打开内嵌窗口：" + str(e) + "\n\n可能需要系统 WebView2 Runtime（Edge 组件）。",
            "D2R RotW Editor - Created By 奈非天的侍从", 0x10)
    finally:
        stop_server()


if __name__ == "__main__":
    main()
