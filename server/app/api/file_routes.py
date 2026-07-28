import os
import string
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/files", tags=["files"])


class FileItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int


class ReadFileRequest(BaseModel):
    path: str


@router.get("/roots", response_model=list[FileItem])
def list_roots():
    """列出可用的根目录（Windows 驱动器或 Unix 根目录）"""
    items = []
    if os.name == "nt":
        import ctypes
        # Windows: list available drives
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1
        for d in drives:
            try:
                p = Path(d)
                if p.exists():
                    # Try to get volume label
                    label = d
                    try:
                        import ctypes.wintypes
                        buf = ctypes.create_unicode_buffer(128)
                        ctypes.windll.kernel32.GetVolumeInformationW(
                            d, buf, 128, None, None, None, None, 0)
                        if buf.value:
                            label = f"{d} ({buf.value})"
                    except Exception:
                        pass
                    items.append(FileItem(name=label, path=d, is_dir=True, size=0))
            except Exception:
                pass
    else:
        # Unix: just "/"
        items.append(FileItem(name="/ (root)", path="/", is_dir=True, size=0))
    return items


@router.get("/list", response_model=list[FileItem])
def list_files(path: str = Query(default=".")):
    """列出指定目录下的文件和子目录"""
    if path == "__ROOTS__":
        return list_roots()
    target = Path(path).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"路径不存在: {path}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"路径不是目录: {path}")

    items = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            try:
                size = entry.stat().st_size if entry.is_file() else 0
            except OSError:
                size = 0
            items.append(FileItem(
                name=entry.name,
                path=str(entry.resolve()),
                is_dir=entry.is_dir(),
                size=size,
            ))
    except PermissionError:
        raise HTTPException(status_code=403, detail="没有权限访问该目录")

    return items


@router.post("/read")
def read_file(req: ReadFileRequest):
    """读取指定文件的内容"""
    target = Path(req.path).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {req.path}")
    if not target.is_file():
        raise HTTPException(status_code=400, detail=f"路径不是文件: {req.path}")

    # 限制文件大小，避免读取超大文件导致内存问题
    max_size = 50 * 1024 * 1024  # 50MB
    try:
        size = target.stat().st_size
    except OSError:
        raise HTTPException(status_code=500, detail="无法读取文件信息")
    if size > max_size:
        raise HTTPException(status_code=400, detail=f"文件过大 ({size} bytes)，超过限制 {max_size} bytes")

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")

    return {
        "path": str(target),
        "name": target.name,
        "size": size,
        "content": content,
    }
