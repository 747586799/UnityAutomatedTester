import hashlib
import json
import logging
import re
import shutil

from app.cleaning_rules import compile_skip_patterns, should_skip_line, clean_common_prefixes
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.models import (
    BattleCompareItem,
    BattleCompareResult,
    ReportCompareItem,
    ReportCompareResult,
    UnityGroupHistoryRecord,
    UnityGroupHistorySummary,
    UnityHistoryRecord,
    UnityHistorySummary,
    UnityInstance,
)

logger = logging.getLogger("unity_automated_tester")


class HistoryStore:
    def __init__(self, runtime_root: Path, battle_log_root: Path | None = None) -> None:
        self.history_root = runtime_root / "history"
        self.groups_root = self.history_root / "groups"
        self.battle_log_root = battle_log_root
        self.history_root.mkdir(parents=True, exist_ok=True)
        self.groups_root.mkdir(parents=True, exist_ok=True)
        self._history_cache: dict[str, list[UnityGroupHistorySummary]] = {"_all": [], "_all_ts": 0.0}
        self._skip_patterns = compile_skip_patterns()

    def set_battle_log_root(self, path: str | None) -> None:
        self.battle_log_root = Path(path) if path else None
        self._history_cache.clear()
        self._history_cache["_all"] = []
        self._history_cache["_all_ts"] = 0.0

    # 閳光偓閳光偓 Group-level archive 閳光偓閳光偓

    def archive_group(
        self,
        group_id: str,
        group_name: str | None,
        instances: list[UnityInstance],
    ) -> str:
        now_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        group_history_id = f"{group_id}-{now_ts}"
        group_dir = self.groups_root / group_history_id
        group_dir.mkdir(parents=True, exist_ok=True)

        _ts = lambda dt: dt.isoformat() if isinstance(dt, datetime) else (str(dt) if dt else None)

        total = len(instances)
        completed = sum(1 for i in instances if i.state.value == "completed")
        failed = total - completed
        group_state = "completed" if completed == total else "failed"

        instance_summaries: list[dict[str, Any]] = []
        inst_dir = group_dir / "instances"
        inst_dir.mkdir(parents=True, exist_ok=True)

        for inst in instances:
            inst_summary = {
                "id": inst.id,
                "launch_name": inst.launch_name,
                "state": inst.state.value,
                "start_time": _ts(inst.start_time),
                "end_time": _ts(inst.end_time),
            }
            instance_summaries.append(inst_summary)
            self._archive_group_instance(inst, inst_dir)

        report_compare = self._compare_group_reports(inst_dir, instances)
        battle_compare = self._compare_battle_logs(inst_dir, instances)

        group_data: dict[str, Any] = {
            "group_id": group_id,
            "group_name": group_name,
            "total": total,
            "completed": completed,
            "failed": failed,
            "state": group_state,
            "created_time": _ts(instances[0].start_time) if instances else "",
            "end_time": _ts(max((i.end_time for i in instances if i.end_time), default=None)),
            "archived_time": _ts(datetime.now()),
            "instances": instance_summaries,
            "report_compare": report_compare.model_dump(mode="json") if report_compare else None,
            "battle_compare": battle_compare.model_dump(mode="json") if battle_compare else None,
        }

        (group_dir / "group.json").write_text(
            json.dumps(group_data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        logger.info("Group archived: group_id=%s -> history/groups/%s", group_id, group_history_id)
        self._cleanup_runtime_group_dir(group_id)
        self._history_cache["_all_ts"] = 0.0  # invalidate
        return group_history_id

    def _cleanup_runtime_group_dir(self, group_id: str) -> None:
        group_dir = self.history_root.parent / "instances" / group_id
        if not group_dir.is_dir():
            return
        try:
            shutil.rmtree(group_dir)
            logger.info("Runtime group dir removed: %s", group_dir)
        except Exception:
            logger.warning("Failed to remove runtime group dir: %s", group_dir, exc_info=True)

    def _archive_group_instance(self, instance: UnityInstance, instances_dir: Path) -> None:
        inst_history_dir = instances_dir / instance.id
        inst_history_dir.mkdir(parents=True, exist_ok=True)
        _ts = lambda dt: dt.isoformat() if isinstance(dt, datetime) else (str(dt) if dt else None)  # noqa: E731

        result = dict(instance.result) if instance.result else None
        report = result.pop("report", None) if result else None
        if report is None and instance.result_file is not None:
            rf = instance.result_file.parent / "report.txt"
            if rf.exists():
                report = rf.read_text(encoding="utf-8", errors="replace")

        if report is not None:
            (inst_history_dir / "report.txt").write_text(str(report), encoding="utf-8", newline="")

        # Extract RoomId from report and find battle log
        battle_log_sha = None
        battle_log_found = False
        room_id = None
        if report is not None and self.battle_log_root is not None:
            room_id = self._extract_room_id(str(report))
            if room_id:
                battle_log_path = self._find_battle_log(room_id, instance.start_time)
                if battle_log_path is not None:
                    try:
                        battle_text = battle_log_path.read_text(encoding="utf-8", errors="replace")
                        cleaned_battle = self._clean_report_text(battle_text)
                        battle_log_sha = hashlib.sha256(cleaned_battle.encode("utf-8")).hexdigest()
                        battle_log_found = True
                        # Save battle log text to group-level instances dir for diff viewing
                        battle_log_dest = instances_dir / "_battle_log.txt"
                        battle_log_dest.write_text(battle_text, encoding="utf-8", newline="")
                    except Exception:
                        logger.warning("Failed to read battle log: %s", battle_log_path, exc_info=True)

        archive_data: dict[str, Any] = {
            "id": instance.id,
            "launch_name": instance.launch_name,
            "group_id": instance.group_id,
            "group_name": instance.group_name,
            "launch_target": instance.launch_target,
            "agent_id": instance.agent_id,
            "project_id": instance.project_id,
            "project_slot_id": instance.project_slot_id,
            "state": instance.state.value,
            "project_path": instance.project_path,
            "unity_executable_path": instance.unity_executable_path,
            "execute_method": instance.execute_method,
            "process_id": instance.process_id,
            "progress": instance.progress,
            "start_time": _ts(instance.start_time),
            "connected_time": _ts(instance.connected_time),
            "end_time": _ts(instance.end_time),
            "exit_code": instance.exit_code,
            "error_message": instance.error_message,
            "args": instance.args,
            "launch_command": instance.launch_command,
            "result": result,
            "logs": instance.logs,
            "ready_id": instance.ready_id,
            "battle_room_id": room_id,
            "battle_log_sha": battle_log_sha,
            "battle_log_found": battle_log_found,
        }
        (inst_history_dir / "archive.json").write_text(
            json.dumps(archive_data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        # Copy runtime instance files (unity.log, result.json, etc.) to history
        if instance.group_id:
            runtime_inst_dir = self.history_root.parent / "instances" / instance.group_id / instance.id
            if runtime_inst_dir.is_dir():
                for src_file in runtime_inst_dir.iterdir():
                    if src_file.is_file():
                        dst = inst_history_dir / src_file.name
                        if not dst.exists():
                            shutil.copy2(src_file, dst)

    def _should_skip_report_line(self, raw_line: str) -> bool:
        return should_skip_line(raw_line, self._skip_patterns)

    def _clean_common_prefixes(self, line: str) -> str:
        return clean_common_prefixes(line)

    def _format_numbers_strict(self, text: str) -> str:
        def replacer(match: re.Match[str]) -> str:
            try:
                val = float(match.group())
                if val == 0:
                    return "0.0000"
                return f"{val:.4f}"
            except Exception:
                return match.group()

        return re.sub(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", replacer, text)

    def _clean_report_line(self, line: str, id_map: dict[str, str]) -> str:
        line = line.strip()
        if not line:
            return ""

        line = re.sub(r"^\[BattleLog_[^\]]+\]\s*", "", line)
        if "[Frame:]" in line:
            line = line.split("[Frame:]", 1)[1]
        else:
            line = re.sub(r"^\d{4}-\d{2}-\d{2}.*?\[[A-Z]+\]\s*", "", line)

        line = self._clean_common_prefixes(line)

        def replace_identify(match: re.Match[str]) -> str:
            original_id = match.group(1)
            if original_id not in id_map:
                id_map[original_id] = str(len(id_map) + 1)
            return f"Identify:__ID_{id_map[original_id]}__"

        line = re.sub(r"Identify:(\d+)", replace_identify, line)
        line = re.sub(r"Version:\d+", "Version:ID", line)
        line = self._format_numbers_strict(line)
        line = re.sub(r"Identify:__ID_(\d+)__", r"Identify:\1", line)
        return line.strip()

    def _clean_report_text(self, text: str) -> str:
        id_map: dict[str, str] = {}
        cleaned_lines: list[str] = []
        for raw_line in text.splitlines()[1:]:  # skip first line
            if self._should_skip_report_line(raw_line):
                continue
            clean_line = self._clean_report_line(raw_line, id_map)
            if clean_line:
                cleaned_lines.append(clean_line)
        return "\n".join(cleaned_lines)

    def _compare_group_reports(self, instances_dir: Path, instances: list[UnityInstance]) -> ReportCompareResult | None:
        reports: list[tuple[str, str | None, str, int]] = []
        for inst in instances:
            report_file = instances_dir / inst.id / "report.txt"
            if report_file.exists():
                text = report_file.read_text(encoding="utf-8", errors="replace")
                cleaned_text = self._clean_report_text(text)
                sha = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
                reports.append((inst.id, inst.launch_name, sha, len(cleaned_text)))

        if not reports:
            return None

        # 单实例：自身作为 baseline，始终一致
        if len(reports) == 1:
            rid, rname, rsha, rlen = reports[0]
            return ReportCompareResult(
                baseline_instance_id=rid,
                same=True,
                items=[ReportCompareItem(
                    instance_id=rid, launch_name=rname,
                    sha256=rsha, same_as_baseline=True,
                    report_length=rlen,
                )],
            )

        # 基于多数(majority)原则确定基线：取出现次数最多的 SHA 对应的实例作为 baseline
        sha_counts = Counter(r[2] for r in reports)
        majority_sha = sha_counts.most_common(1)[0][0]
        all_same = len(sha_counts) == 1

        # 取第一个 majority SHA 的实例作为 baseline
        baseline_id = next(r[0] for r in reports if r[2] == majority_sha)

        items = [
            ReportCompareItem(
                instance_id=rid,
                launch_name=rname,
                sha256=rsha,
                same_as_baseline=rsha == majority_sha,
                report_length=report_length,
            )
            for rid, rname, rsha, report_length in reports
        ]

        return ReportCompareResult(
            baseline_instance_id=baseline_id,
            same=all_same,
            items=items,
        )

    def _compare_archived_group_reports(self, instances_dir: Path, instances_data: list[dict[str, Any]]) -> ReportCompareResult | None:
        reports: list[tuple[str, str | None, str, int]] = []
        for inst in instances_data:
            inst_id = inst.get("id")
            if not inst_id:
                continue
            report_file = instances_dir / inst_id / "report.txt"
            if report_file.exists():
                text = report_file.read_text(encoding="utf-8", errors="replace")
                cleaned_text = self._clean_report_text(text)
                sha = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
                reports.append((inst_id, inst.get("launch_name"), sha, len(cleaned_text)))

        if not reports:
            return None

        if len(reports) == 1:
            rid, rname, rsha, rlen = reports[0]
            return ReportCompareResult(
                baseline_instance_id=rid,
                same=True,
                items=[ReportCompareItem(
                    instance_id=rid,
                    launch_name=rname,
                    sha256=rsha,
                    same_as_baseline=True,
                    report_length=rlen,
                )],
            )

        sha_counts = Counter(r[2] for r in reports)
        majority_sha = sha_counts.most_common(1)[0][0]
        baseline_id = next(r[0] for r in reports if r[2] == majority_sha)
        return ReportCompareResult(
            baseline_instance_id=baseline_id,
            same=len(sha_counts) == 1,
            items=[
                ReportCompareItem(
                    instance_id=rid,
                    launch_name=rname,
                    sha256=rsha,
                    same_as_baseline=rsha == majority_sha,
                    report_length=report_length,
                )
                for rid, rname, rsha, report_length in reports
            ],
        )

    def _extract_room_id(self, report_text: str) -> str | None:
        m = re.search(r"RoomId:([0-9A-Fa-f]+)", report_text)
        return m.group(1) if m else None

    def _find_battle_log(self, room_id: str, start_time: datetime) -> Path | None:
        return self._find_battle_log_in_root(room_id, start_time, self.battle_log_root)

    def _find_battle_log_in_root(self, room_id: str, start_time: datetime, battle_log_root: Path | None) -> Path | None:
        if battle_log_root is None:
            return None
        date_str = start_time.strftime("%y-%m-%d")
        log_path = battle_log_root / date_str / f"BattleLog_{room_id}.log"
        return log_path if log_path.exists() else None

    def _compare_battle_logs(self, instances_dir: Path, instances: list[UnityInstance]) -> BattleCompareResult | None:
        if self.battle_log_root is None:
            return None

        report_pairs: list[tuple[str, str | None, str, int, str | None, int]] = []
        # (instance_id, launch_name, report_sha, report_len, battle_sha, battle_len)
        room_id: str | None = None
        missing = False

        for inst in instances:
            inst_dir = instances_dir / inst.id
            report_file = inst_dir / "report.txt"
            archive_file = inst_dir / "archive.json"

            if not report_file.exists():
                continue

            text = report_file.read_text(encoding="utf-8", errors="replace")
            cleaned_text = self._clean_report_text(text)
            report_sha = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

            # Read battle log sha from archive.json
            battle_sha = None
            battle_len = 0
            if archive_file.exists():
                try:
                    archive = json.loads(archive_file.read_text(encoding="utf-8"))
                    if archive.get("battle_log_found"):
                        battle_sha = archive.get("battle_log_sha")
                        battle_len = len(archive.get("battle_log_sha", ""))
                    else:
                        missing = True
                    if archive.get("battle_room_id"):
                        room_id = archive["battle_room_id"]
                except Exception:
                    missing = True
            else:
                missing = True

            report_pairs.append((inst.id, inst.launch_name, report_sha, len(cleaned_text), battle_sha, battle_len))

        if not report_pairs:
            return None

        all_battle_found = all(r[4] is not None for r in report_pairs)
        if not all_battle_found and len([r for r in report_pairs if r[4] is not None]) == 0:
            return None  # no battle logs at all

        items = []
        for rid, rname, rsha, rlen, bsha, _blen in report_pairs:
            match = (bsha is not None and rsha == bsha)
            items.append(BattleCompareItem(
                instance_id=rid,
                launch_name=rname,
                report_sha256=rsha,
                battle_sha256=bsha,
                match=match,
                report_length=rlen,
                battle_length=0,  # we don't read full battle text here, SHA is sufficient
            ))

        all_match = all(item.match for item in items)

        return BattleCompareResult(
            all_match=all_match,
            battle_room_id=room_id,
            battle_log_missing=missing,
            items=items,
        )

    def refresh_group_battle_logs(self, group_history_id: str, battle_log_root: str | None = None) -> BattleCompareResult | None:
        group_dir = self.groups_root / group_history_id
        group_file = group_dir / "group.json"
        if not group_file.exists():
            return None

        root = Path(battle_log_root) if battle_log_root else self.battle_log_root
        if root is None:
            return None

        data = json.loads(group_file.read_text(encoding="utf-8"))
        instances_dir = group_dir / "instances"
        battle_log_text: str | None = None

        for inst_data in data.get("instances", []):
            inst_id = inst_data.get("id")
            if not inst_id:
                continue
            inst_dir = instances_dir / inst_id
            archive_file = inst_dir / "archive.json"
            report_file = inst_dir / "report.txt"
            if not archive_file.exists() or not report_file.exists():
                continue

            archive = json.loads(archive_file.read_text(encoding="utf-8"))
            report = report_file.read_text(encoding="utf-8", errors="replace")
            room_id = archive.get("battle_room_id") or self._extract_room_id(report)
            start_time_text = archive.get("start_time") or inst_data.get("start_time")
            if not room_id or not start_time_text:
                continue
            start_time = datetime.fromisoformat(str(start_time_text))
            battle_log_path = self._find_battle_log_in_root(room_id, start_time, root)
            if battle_log_path is None:
                archive["battle_room_id"] = room_id
                archive["battle_log_found"] = False
                archive["battle_log_sha"] = None
            else:
                battle_log_text = battle_log_path.read_text(encoding="utf-8", errors="replace")
                cleaned_battle = self._clean_report_text(battle_log_text)
                archive["battle_room_id"] = room_id
                archive["battle_log_found"] = True
                archive["battle_log_sha"] = hashlib.sha256(cleaned_battle.encode("utf-8")).hexdigest()
            archive_file.write_text(json.dumps(archive, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        if battle_log_text is not None:
            (instances_dir / "_battle_log.txt").write_text(battle_log_text, encoding="utf-8", newline="")

        previous_root = self.battle_log_root
        self.battle_log_root = root
        try:
            battle_compare = self._compare_battle_logs(instances_dir, [UnityInstance.model_validate({
                "id": inst.get("id"),
                "launch_name": inst.get("launch_name"),
                "project_path": "",
                "unity_executable_path": "",
                "execute_method": "",
            }) for inst in data.get("instances", []) if inst.get("id")])
        finally:
            self.battle_log_root = previous_root

        data["battle_compare"] = battle_compare.model_dump(mode="json") if battle_compare else None
        group_file.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self._history_cache["_all_ts"] = 0.0
        return battle_compare

    def list_group_history(self, page: int = 1, page_size: int = 20) -> tuple[list[UnityGroupHistorySummary], int]:
        results = self._load_all_group_history()
        total = len(results)
        start = (page - 1) * page_size
        paged = results[start : start + page_size]
        return paged, total

    def _load_all_group_history(self) -> list[UnityGroupHistorySummary]:
        import time
        now = time.time()
        cached = self._history_cache.get("_all", [])
        if now - self._history_cache.get("_all_ts", 0) < 5 and all(item.start_time and item.end_time for item in cached):
            return cached
        results: list[UnityGroupHistorySummary] = []
        for entry in self.groups_root.iterdir():
            if not entry.is_dir():
                continue
            group_file = entry / "group.json"
            if not group_file.exists():
                continue
            try:
                data = json.loads(group_file.read_text(encoding="utf-8"))
                rc = data.get("report_compare")
                bc = data.get("battle_compare")
                instances_data = data.get("instances", [])
                start_times = [item.get("start_time") for item in instances_data if item.get("start_time")]
                end_times = [item.get("end_time") for item in instances_data if item.get("end_time")]
                start_time = data.get("start_time") or data.get("created_time") or (min(start_times) if start_times else "")
                end_time = data.get("end_time") or (max(end_times) if end_times else data.get("archived_time", ""))
                if data.get("start_time") != start_time or data.get("end_time") != end_time:
                    data["start_time"] = start_time
                    data["end_time"] = end_time
                    group_file.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                results.append(UnityGroupHistorySummary(
                    history_id=entry.name,
                    group_id=data.get("group_id", entry.name),
                    group_name=data.get("group_name"),
                    total=data.get("total", 0),
                    completed=data.get("completed", 0),
                    failed=data.get("failed", 0),
                    state=data.get("state", ""),
                    start_time=start_time,
                    end_time=end_time,
                    archived_time=data.get("archived_time", ""),
                    report_same=rc.get("same") if rc else None,
                    battle_match=bc.get("all_match") if bc else None,
                ))
            except Exception:
                logger.warning("Failed to read group archive: %s", group_file, exc_info=True)
        results.sort(key=lambda r: r.archived_time or "", reverse=True)
        self._history_cache["_all"] = results
        self._history_cache["_all_ts"] = now
        return results

    def find_latest_group_history_id(self, group_id: str) -> str | None:
        matches = [item for item in self._load_all_group_history() if item.group_id == group_id]
        return matches[0].history_id if matches else None

    def delete_group_history(self, group_history_id: str) -> bool:
        group_dir = self.groups_root / group_history_id
        if not group_dir.is_dir():
            return False
        shutil.rmtree(group_dir)
        self._history_cache["_all_ts"] = 0.0
        return True

    def delete_group_histories(self, group_history_ids: list[str]) -> dict[str, list[str]]:
        result = {"deleted": [], "missing": [], "failed": []}
        for history_id in group_history_ids:
            try:
                if self.delete_group_history(history_id):
                    result["deleted"].append(history_id)
                else:
                    result["missing"].append(history_id)
            except Exception:
                logger.warning("Failed to delete group archive: %s", history_id, exc_info=True)
                result["failed"].append(history_id)
        return result

    def get_group_history(self, group_history_id: str) -> UnityGroupHistoryRecord | None:
        group_dir = self.groups_root / group_history_id
        group_file = group_dir / "group.json"
        if not group_file.exists():
            return None
        try:
            data = json.loads(group_file.read_text(encoding="utf-8"))
            instance_summaries: list[UnityHistorySummary] = []
            instance_reports: dict[str, str] = {}
            for inst_data in data.get("instances", []):
                id_ = inst_data["id"]
                inst_archive = group_dir / "instances" / id_ / "archive.json"
                report_file = group_dir / "instances" / id_ / "report.txt"
                report = report_file.read_text(encoding="utf-8", errors="replace") if report_file.exists() else None
                if report:
                    instance_reports[id_] = report
                if inst_archive.exists():
                    inst = json.loads(inst_archive.read_text(encoding="utf-8"))
                    instance_summaries.append(UnityHistorySummary(
                        id=id_,
                        original_id=id_,
                        state=inst.get("state", inst_data.get("state", "unknown")),
                        project_path=inst.get("project_path", ""),
                        execute_method=inst.get("execute_method", ""),
                        process_id=inst.get("process_id"),
                        progress=inst.get("progress", 0.0),
                        start_time=inst.get("start_time", ""),
                        end_time=inst.get("end_time"),
                        archived_time=data.get("archived_time", ""),
                        error_message=inst.get("error_message"),
                    ))
                else:
                    instance_summaries.append(UnityHistorySummary(
                        id=id_,
                        original_id=id_,
                        state=inst_data.get("state", "unknown"),
                        project_path="",
                        execute_method="",
                        archived_time="",
                    ))

            rc_data = data.get("report_compare")
            report_compare = ReportCompareResult(**rc_data) if rc_data else None
            if report_compare is None:
                report_compare = self._compare_archived_group_reports(group_dir / "instances", data.get("instances", []))

            bc_data = data.get("battle_compare")
            battle_compare = BattleCompareResult(**bc_data) if bc_data else None

            instances_data = data.get("instances", [])
            start_times = [item.get("start_time") for item in instances_data if item.get("start_time")]
            end_times = [item.get("end_time") for item in instances_data if item.get("end_time")]
            start_time = data.get("start_time") or data.get("created_time") or (min(start_times) if start_times else "")
            end_time = data.get("end_time") or (max(end_times) if end_times else data.get("archived_time", ""))

            # Read battle log text if archived
            battle_log_file = group_dir / "instances" / "_battle_log.txt"
            if battle_log_file.exists():
                try:
                    instance_reports["__battle_log__"] = battle_log_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    logger.warning("Failed to read battle log: %s", battle_log_file, exc_info=True)

            return UnityGroupHistoryRecord(
                summary=UnityGroupHistorySummary(
                    history_id=group_history_id,
                    group_id=data.get("group_id", group_history_id),
                    group_name=data.get("group_name"),
                    total=data.get("total", 0),
                    completed=data.get("completed", 0),
                    failed=data.get("failed", 0),
                    state=data.get("state", ""),
                    start_time=start_time,
                    end_time=end_time,
                    archived_time=data.get("archived_time", ""),
                    report_same=report_compare.same if report_compare else None,
                    battle_match=battle_compare.all_match if battle_compare else None,
                ),
                instances=instance_summaries,
                report_compare=report_compare,
                battle_compare=battle_compare,
                instance_reports=instance_reports,
            )
        except Exception:
            logger.warning("Failed to read group history: %s", group_file, exc_info=True)
            return None

    def get_group_instance_history(self, group_history_id: str, instance_id: str) -> UnityHistoryRecord | None:
        """Get a single instance's history record from a group archive."""
        inst_dir = self.groups_root / group_history_id / "instances" / instance_id
        archive_file = inst_dir / "archive.json"
        if not archive_file.exists():
            return None
        try:
            data = json.loads(archive_file.read_text(encoding="utf-8"))
            report_file = inst_dir / "report.txt"
            report = report_file.read_text(encoding="utf-8", errors="replace") if report_file.exists() else None

            result = data.get("result")
            if report is not None:
                result = dict(result or {})
                result["report"] = report

            group_data_file = self.groups_root / group_history_id / "group.json"
            archived_time = ""
            if group_data_file.exists():
                try:
                    group_data = json.loads(group_data_file.read_text(encoding="utf-8"))
                    archived_time = group_data.get("archived_time", "")
                except Exception:
                    pass

            return UnityHistoryRecord(
                summary=UnityHistorySummary(
                    id=data.get("id", instance_id),
                    original_id=data.get("id", instance_id),
                    state=data.get("state", "unknown"),
                    project_path=data.get("project_path", ""),
                    execute_method=data.get("execute_method", ""),
                    process_id=data.get("process_id"),
                    progress=data.get("progress", 0.0),
                    start_time=data.get("start_time", ""),
                    end_time=data.get("end_time"),
                    archived_time=archived_time,
                    error_message=data.get("error_message"),
                ),
                result=result,
                report=report,
                error_message=data.get("error_message"),
                logs=data.get("logs", []),
                launch_command=data.get("launch_command", []),
                args=data.get("args", {}),
                unity_executable_path=data.get("unity_executable_path"),
                group_id=data.get("group_id"),
                group_name=data.get("group_name"),
                launch_name=data.get("launch_name"),
            )
        except Exception:
            logger.warning("Failed to read group instance archive: %s", archive_file, exc_info=True)
            return None
