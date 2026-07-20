"""JobHandle 数据模型单元测试"""

import pytest
from datetime import datetime

from masgent.models.job import JobHandle


class TestJobHandle:
    def test_roundtrip_serialization(self):
        """验证 JobHandle → dict → JobHandle 往返一致"""
        handle = JobHandle(
            job_id="local_abc123",
            backend="local",
            pid=12345,
            scheduler_id="slurm_67890",
            submitted_at="2026-06-22T10:00:00",
            metadata={"command": "vasp_std", "nodes": 1},
        )

        data = handle.to_dict()
        restored = JobHandle.from_dict(data)

        assert restored.job_id == "local_abc123"
        assert restored.backend == "local"
        assert restored.pid == 12345
        assert restored.scheduler_id == "slurm_67890"
        assert restored.submitted_at == "2026-06-22T10:00:00"
        assert restored.metadata["command"] == "vasp_std"
        assert restored.metadata["nodes"] == 1

    def test_from_dict_missing_fields_use_defaults(self):
        """验证从字典重建时缺失字段使用默认值（兼容旧数据）"""
        data = {
            "job_id": "legacy_job",
            # 缺少 backend, pid, scheduler_id, submitted_at, metadata
        }
        restored = JobHandle.from_dict(data)

        assert restored.job_id == "legacy_job"
        assert restored.backend == "local"  # 默认值
        assert restored.pid is None
        assert restored.scheduler_id is None
        assert restored.submitted_at is None
        assert restored.metadata == {}

    def test_now_timestamp(self):
        """验证 now() 返回有效的 ISO 时间戳"""
        ts = JobHandle.now()
        # 简单格式检查
        assert "T" in ts
        # 尝试解析
        datetime.fromisoformat(ts)

    def test_to_dict_excludes_none(self):
        """验证序列化时 None 值仍会出现在 dict 中（asdict 特性）"""
        handle = JobHandle(job_id="test", backend="local")
        data = handle.to_dict()
        assert "pid" in data
        assert data["pid"] is None
        assert "scheduler_id" in data
        assert data["scheduler_id"] is None