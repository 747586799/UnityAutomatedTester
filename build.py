"""
一键打包脚本：将 Server 和 Agent 打包为独立的 exe 文件。

依赖安装：
    pip install pyinstaller

用法：
    python build.py                    # 打包为 exe，输出到 dist/
    python build.py --no-exe           # 只复制源码，不打包 exe
    python build.py --out-dir ./my-pkg # 指定输出目录
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SERVER_DIR = PROJECT_ROOT / "server"
AGENT_DIR = PROJECT_ROOT / "agent"
DIST_DIR = PROJECT_ROOT / "dist"


def clean():
    """清理之前打包的文件"""
    for p in [DIST_DIR, PROJECT_ROOT / "build"]:
        shutil.rmtree(p, ignore_errors=True)
    for spec in PROJECT_ROOT.glob("*.spec"):
        spec.unlink(missing_ok=True)


def get_version() -> str:
    """获取版本号"""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "0.1.0"


def check_pyinstaller():
    """检查 PyInstaller 是否安装"""
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("PyInstaller 未安装，正在安装...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            check=True, cwd=PROJECT_ROOT,
        )


def build_server_exe(version: str) -> Path:
    """打包 Server 为 exe"""
    print("=" * 60)
    print("打包 Server...")
    print("=" * 60)

    # 数据文件：web 目录
    web_dir = SERVER_DIR / "app" / "web"
    datas = []
    if web_dir.is_dir():
        datas.append((str(web_dir), "app/web"))

    # hidden imports
    hidden_imports = [
        "app.agents",
        "app.agents.models",
        "app.agents.registry",
        "app.agents.dispatcher",
        "app.agents.routes",
        "app.agents.websocket",
        "app.api",
        "app.api.unity_routes",
        "app.automation",
        "app.automation.models",
        "app.automation.routes",
        "app.automation.scheduler",
        "app.automation.store",
        "app.automation.template_store",
        "app.core",
        "app.core.models",
        "app.core.manager",
        "app.core.launcher",
        "app.core.dispatcher",
        "app.core.registry",
        "app.core.states",
        "app.protocol",
        "app.protocol.messages",
        "app.protocol.types",
        "app.runtime",
        "app.runtime.history_store",
        "app.runtime.launch_config",
        "app.runtime.workspace",
        "app.websocket",
        "app.websocket.unity_socket",
        "app.web",
        "uvicorn",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.middleware",
        "uvicorn.middleware.wsgi",
    ]

    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", f"UnityAutomatedTester_Server_v{version}",
        "--distpath", str(DIST_DIR),
        "--workpath", str(PROJECT_ROOT / "build"),
        "--specpath", str(PROJECT_ROOT),
        "--add-data", f"{SERVER_DIR / 'app' / 'web'}{os.pathsep}app/web",
        "--clean",
        "--noconfirm",
    ]
    for mod in hidden_imports:
        args.extend(["--hidden-import", mod])

    args.append(str(SERVER_DIR / "run_server.py"))

    print(f"执行: {' '.join(args)}")
    subprocess.run(args, check=True, cwd=PROJECT_ROOT)

    exe_name = f"UnityAutomatedTester_Server_v{version}.exe"
    exe_path = DIST_DIR / exe_name
    # PyInstaller 可能有 .exe 后缀
    if not exe_path.exists():
        exe_path = DIST_DIR / f"UnityAutomatedTester_Server_v{version}"
    print(f"Server 打包完成: {exe_path}")
    return exe_path


def build_agent_exe(version: str) -> Path:
    """打包 Agent 为 exe"""
    print("=" * 60)
    print("打包 Agent...")
    print("=" * 60)

    hidden_imports = [
        "app.models",
        "app.config",
        "app.launcher",
        "app.server_client",
    ]

    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", f"UnityAutomatedTester_Agent_v{version}",
        "--distpath", str(DIST_DIR),
        "--workpath", str(PROJECT_ROOT / "build"),
        "--specpath", str(PROJECT_ROOT),
        "--add-data", f"{AGENT_DIR / 'agent.config.json'}{os.pathsep}.",
        "--clean",
        "--noconfirm",
    ]
    for mod in hidden_imports:
        args.extend(["--hidden-import", mod])

    args.append(str(AGENT_DIR / "app" / "main.py"))

    print(f"执行: {' '.join(args)}")
    subprocess.run(args, check=True, cwd=PROJECT_ROOT)

    exe_name = f"UnityAutomatedTester_Agent_v{version}.exe"
    exe_path = DIST_DIR / exe_name
    if not exe_path.exists():
        exe_path = DIST_DIR / f"UnityAutomatedTester_Agent_v{version}"
    print(f"Agent 打包完成: {exe_path}")
    return exe_path


def copy_source_only(out_dir: Path, version: str):
    """只复制源码（不打包 exe 时的回退方案）"""
    pkg_dir = out_dir / f"UnityAutomatedTester_v{version}"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # 复制 server
    shutil.copytree(SERVER_DIR, pkg_dir / "server", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "*.pyc",
    ))
    # 复制 agent
    shutil.copytree(AGENT_DIR, pkg_dir / "agent", ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc",
    ))
    # 复制 README
    readme = PROJECT_ROOT / "README.md"
    if readme.exists():
        shutil.copy2(readme, pkg_dir / "README.md")

    # 创建启动脚本
    (pkg_dir / "start_server.bat").write_text(
        '@echo off\n'
        'cd /d "%~dp0server"\n'
        'echo 正在启动 Server...\n'
        'python -m uvicorn app.main:app --host 127.0.0.1 --port 5100\n'
        'pause\n',
        encoding="utf-8",
    )
    (pkg_dir / "start_agent.bat").write_text(
        '@echo off\n'
        'cd /d "%~dp0agent"\n'
        'echo 正在启动 Agent...\n'
        'python -m app.main\n'
        'pause\n',
        encoding="utf-8",
    )

    print(f"源码已复制到: {pkg_dir}")
    return pkg_dir


def main():
    parser = argparse.ArgumentParser(description="打包 UnityAutomatedTester")
    parser.add_argument("--no-exe", action="store_true", help="只复制源码，不打包 exe")
    parser.add_argument("--out-dir", type=str, default=str(DIST_DIR), help="输出目录")
    parser.add_argument("--version", type=str, default="", help="自定义版本号")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    version = args.version or get_version()
    print(f"版本: {version}")
    print(f"输出目录: {out_dir}")

    if args.no_exe:
        copy_source_only(out_dir, version)
        return

    # 打包 exe
    check_pyinstaller()
    clean()

    # 先创建 run_server.py 入口文件（因为 PyInstaller 需要一个主入口）
    run_server_py = SERVER_DIR / "run_server.py"
    run_server_py.write_text(
        '"""PyInstaller 入口文件，支持 --host 和 --port 参数"""\n'
        'import sys\n'
        'import argparse\n'
        'from pathlib import Path\n'
        'sys.path.insert(0, str(Path(__file__).parent))\n'
        'import uvicorn\n'
        'from app.main import app\n'
        'if __name__ == "__main__":\n'
        '    parser = argparse.ArgumentParser(description="Unity Automated Tester Server")\n'
        '    parser.add_argument("--host", type=str, default="127.0.0.1", help="监听地址，例如 192.168.1.15")\n'
        '    parser.add_argument("--port", type=int, default=5100, help="监听端口")\n'
        '    args = parser.parse_args()\n'
        '    uvicorn.run(app, host=args.host, port=args.port, ws_ping_interval=20, ws_ping_timeout=30)\n',
        encoding="utf-8",
    )

    try:
        build_server_exe(version)
        build_agent_exe(version)

        # 复制 agent.config.json 到 dist 目录
        agent_config = AGENT_DIR / "agent.config.json"
        if agent_config.exists():
            shutil.copy2(agent_config, DIST_DIR / "agent.config.json")

        print("\n" + "=" * 60)
        print("全部打包完成！")
        print("=" * 60)
        print(f"\n输出目录: {out_dir}")
        for f in sorted(out_dir.iterdir()):
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  {f.name} ({size_mb:.1f} MB)")
    finally:
        # 清理临时入口文件
        if run_server_py.exists():
            run_server_py.unlink()


if __name__ == "__main__":
    main()
