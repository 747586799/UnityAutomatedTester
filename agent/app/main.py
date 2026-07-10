import asyncio
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from app.config import load_config, save_config
from app.models import AgentConfig, ProjectSlotConfig
from app.server_client import AgentServerClient


class AgentUi:
    def __init__(self) -> None:
        self.config = load_config()
        self.project_slots = list(self.config.project_slots)
        self.client: AgentServerClient | None = None
        self.thread: threading.Thread | None = None

        self.root = tk.Tk()
        self.root.title("Unity Automated Tester Agent")
        self.root.geometry("1020x560")

        self.agent_id = tk.StringVar(value=self.config.agent_id)
        self.server_id = tk.StringVar(value=self.config.server_id)
        self.server_url = tk.StringVar(value=self.config.server_url)
        self.unity_server_url = tk.StringVar(value=self.config.unity_server_url)
        self.status = tk.StringVar(value="未连接")

        self._build()
        self._refresh_slots()

    def run(self) -> None:
        self.root.mainloop()

    def _build(self) -> None:
        form = tk.Frame(self.root, padx=12, pady=12)
        form.pack(fill=tk.BOTH, expand=True)

        self._row(form, "Agent ID", self.agent_id, 0)
        self._row(form, "Server 服务端 ID", self.server_id, 1)
        self._row(form, "Server Agent WS", self.server_url, 2)
        self._row(form, "Unity Server WS", self.unity_server_url, 3)

        slots_header = tk.Frame(form)
        slots_header.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 6))
        tk.Label(slots_header, text="项目实例", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(slots_header, text="＋ 添加", command=self.open_add_slot_dialog).pack(side=tk.RIGHT, padx=4)
        tk.Button(slots_header, text="－ 删除", command=self.remove_selected_slot).pack(side=tk.RIGHT, padx=4)

        columns = ("slot_id", "project_id", "state", "unity_executable_path", "project_path")
        self.slots_tree = ttk.Treeview(form, columns=columns, show="headings", height=10)
        self.slots_tree.heading("slot_id", text="slot_id(自动)")
        self.slots_tree.heading("project_id", text="project_id")
        self.slots_tree.heading("state", text="状态")
        self.slots_tree.heading("unity_executable_path", text="unity_executable_path")
        self.slots_tree.heading("project_path", text="project_path")
        self.slots_tree.column("slot_id", width=150, anchor=tk.W)
        self.slots_tree.column("project_id", width=140, anchor=tk.W)
        self.slots_tree.column("state", width=80, anchor=tk.CENTER)
        self.slots_tree.column("unity_executable_path", width=280, anchor=tk.W)
        self.slots_tree.column("project_path", width=280, anchor=tk.W)
        self.slots_tree.grid(row=5, column=0, columnspan=2, sticky="nsew")

        yscroll = ttk.Scrollbar(form, orient=tk.VERTICAL, command=self.slots_tree.yview)
        yscroll.grid(row=5, column=2, sticky="ns")
        self.slots_tree.configure(yscrollcommand=yscroll.set)

        buttons = tk.Frame(form)
        buttons.grid(row=6, column=1, sticky="ew", pady=8)
        tk.Button(buttons, text="保存配置", command=self.save).pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="连接 Server", command=self.connect).pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="同步项目实例", command=self.sync_slots).pack(side=tk.LEFT, padx=4)
        tk.Label(buttons, textvariable=self.status).pack(side=tk.LEFT, padx=12)

        form.columnconfigure(1, weight=1)
        form.rowconfigure(5, weight=1)

    def _row(self, parent: tk.Frame, label: str, variable: tk.StringVar, row: int) -> None:
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        tk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)

    def _last_slot(self) -> ProjectSlotConfig | None:
        return self.project_slots[-1] if self.project_slots else None

    def open_add_slot_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("添加项目实例")
        dialog.geometry("620x240")
        dialog.transient(self.root)
        dialog.grab_set()

        last = self._last_slot()
        project_id = tk.StringVar(value=last.project_id if last else "")
        unity_executable_path = tk.StringVar(value=last.unity_executable_path if last else "")
        project_path = tk.StringVar(value=last.project_path if last else "")

        body = tk.Frame(dialog, padx=12, pady=12)
        body.pack(fill=tk.BOTH, expand=True)
        self._row(body, "project_id", project_id, 0)
        self._row(body, "unity_executable_path", unity_executable_path, 1)
        self._row(body, "project_path", project_path, 2)

        actions = tk.Frame(body)
        actions.grid(row=3, column=1, sticky="e", pady=12)
        tk.Button(actions, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=4)
        tk.Button(
            actions,
            text="添加",
            command=lambda: self._add_slot_from_dialog(dialog, project_id, unity_executable_path, project_path),
        ).pack(side=tk.RIGHT, padx=4)
        body.columnconfigure(1, weight=1)

    def _add_slot_from_dialog(
        self,
        dialog: tk.Toplevel,
        project_id: tk.StringVar,
        unity_executable_path: tk.StringVar,
        project_path: tk.StringVar,
    ) -> None:
        project_id_value = project_id.get().strip()
        unity_executable_path_value = unity_executable_path.get().strip()
        project_path_value = project_path.get().strip()
        if not project_id_value or not unity_executable_path_value or not project_path_value:
            messagebox.showerror("添加失败", "project_id、unity_executable_path、project_path 均不能为空")
            return

        self.project_slots.append(ProjectSlotConfig(
            slot_id=self._next_slot_id(project_id_value),
            project_id=project_id_value,
            unity_executable_path=unity_executable_path_value,
            project_path=project_path_value,
            state="idle",
        ))
        self._refresh_slots()
        dialog.destroy()

    def remove_selected_slot(self) -> None:
        selected = self.slots_tree.selection()
        if not selected:
            messagebox.showinfo("未选择", "请先选择一个项目实例")
            return
        selected_ids = set(selected)
        removable = [slot for slot in self.project_slots if slot.slot_id in selected_ids]
        busy = [slot for slot in removable if slot.state != "idle"]
        if busy:
            messagebox.showwarning("删除失败", f"项目实例 {', '.join(b.slot_id for b in busy)} 当前状态为 {busy[0].state}，不可删除")
            return
        self.project_slots = [slot for slot in self.project_slots if slot.slot_id not in selected_ids]
        self._refresh_slots()

    def _refresh_slots(self) -> None:
        for item in self.slots_tree.get_children():
            self.slots_tree.delete(item)
        for slot in self.project_slots:
            state_text = slot.state
            self.slots_tree.insert(
                "",
                tk.END,
                iid=slot.slot_id,
                values=(slot.slot_id, slot.project_id, state_text, slot.unity_executable_path, slot.project_path),
            )

    def _next_slot_id(self, project_id: str) -> str:
        prefix = self._safe_id(project_id)
        used = {slot.slot_id for slot in self.project_slots}
        index = 1
        while True:
            slot_id = f"{prefix}-{index:02d}"
            if slot_id not in used:
                return slot_id
            index += 1

    def _safe_id(self, value: str) -> str:
        safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
        while "--" in safe:
            safe = safe.replace("--", "-")
        return safe or "project"

    def save(self) -> None:
        try:
            self._save_silent()
            messagebox.showinfo("保存成功", "Agent 配置已保存")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def _save_silent(self) -> None:
        self.config = AgentConfig(
            agent_id=self.agent_id.get().strip(),
            server_id=self.server_id.get().strip(),
            server_url=self.server_url.get().strip(),
            unity_server_url=self.unity_server_url.get().strip(),
            project_slots=self.project_slots,
        )
        save_config(self.config)

    def _on_connected(self) -> None:
        self.root.after(0, lambda: self.status.set("连接成功"))

    def connect(self) -> None:
        self.save()
        if self.thread and self.thread.is_alive():
            messagebox.showinfo("已连接", "Agent 正在运行")
            return
        self.client = AgentServerClient(self.config, on_connected=self._on_connected)
        self.thread = threading.Thread(target=lambda: asyncio.run(self.client.run()), daemon=True)
        self.thread.start()
        self.status.set("连接中")

    def sync_slots(self) -> None:
        if self.client is None:
            messagebox.showinfo("未连接", "请先连接 Server")
            return
        loop = getattr(self.client, "_loop", None)
        if loop is None or not loop.is_running():
            messagebox.showinfo("未连接", "Agent 未成功连接到 Server")
            return
        # 直接发送 UI 中的 project_slots 数据，不依赖 client.config 引用
        self.config.project_slots = self.project_slots
        self._save_silent()
        slots_json = [slot.model_dump(mode="json") for slot in self.project_slots]
        asyncio.run_coroutine_threadsafe(self.client.send_sync_slots(slots_json), loop)


def main() -> None:
    AgentUi().run()


if __name__ == "__main__":
    main()
