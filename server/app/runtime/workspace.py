from pathlib import Path


class RuntimeWorkspace:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root
        self.instances_root = runtime_root / "instances"
        self.instances_root.mkdir(parents=True, exist_ok=True)

    def create_instance_dir(self, instance_id: str) -> Path:
        instance_dir = self.instances_root / instance_id
        instance_dir.mkdir(parents=True, exist_ok=True)
        return instance_dir

    def create_group_instance_dir(self, group_id: str, instance_id: str) -> Path:
        instance_dir = self.instances_root / group_id / instance_id
        instance_dir.mkdir(parents=True, exist_ok=True)
        return instance_dir

    def unity_log_path(self, instance_id: str) -> Path:
        return self.create_instance_dir(instance_id) / "unity.log"

    def result_path(self, instance_id: str) -> Path:
        return self.create_instance_dir(instance_id) / "result.json"

    def group_unity_log_path(self, group_id: str, instance_id: str) -> Path:
        return self.create_group_instance_dir(group_id, instance_id) / "unity.log"

    def group_result_path(self, group_id: str, instance_id: str) -> Path:
        return self.create_group_instance_dir(group_id, instance_id) / "result.json"
