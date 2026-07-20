"""工作目录管理器——统一管理 Calculator 的工作目录生命周期"""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime
from pymatgen.core import Structure

from masgent.models.enums import WorkflowType
from masgent.utils.fingerprint import structure_hash
from masgent._config import config


class WorkDirManager:
    """
    工作目录管理器

    根据 structure + workflow_type 生成确定性路径，
    确保相同计算总能复现到同一目录。
    fingerprint 不参与路径，只写入元数据。
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or config.get_runs_dir()

    def _get_structure_hash(self, structure: Structure) -> str:
        """生成结构的确定性哈希（复用 fingerprint 模块）"""
        return structure_hash(structure)

    def create(
        self,
        structure: Structure,
        workflow_type: WorkflowType,
        mode: Literal["reuse", "overwrite", "new"] = "reuse",
        subdir: Optional[str] = None,
    ) -> Path:
        """
        创建工作目录

        Args:
            structure: 要计算的结构
            workflow_type: 工作流类型（决定子目录名）
            mode: 目录创建模式
                - "reuse": 复用已有目录（默认）
                - "overwrite": 删除并重建
                - "new": 创建新目录（如 run_001, run_002）
            subdir: 额外的子目录（如 specific_vasp_set）

        Returns:
            Path: 工作目录绝对路径
        """
        # 1. 基础目录：formula/工作流类型/
        formula = structure.composition.reduced_formula
        base_path = self.base_dir / formula / workflow_type.value

        # 2. 结构哈希子目录
        struct_hash = self._get_structure_hash(structure)
        base_work_dir = base_path / struct_hash

        # 3. 如果有额外的子目录，追加
        if subdir:
            base_work_dir = base_work_dir / subdir

        # 4. 根据 mode 确定最终路径
        if mode == "new":
            # 生成 run_001, run_002 等
            existing = list(base_work_dir.parent.glob(f"{base_work_dir.name}_*"))
            max_num = 0
            for p in existing:
                try:
                    num = int(p.name.split("_")[-1])
                    max_num = max(max_num, num)
                except ValueError:
                    continue
            work_dir = base_work_dir.parent / f"{base_work_dir.name}_{max_num + 1:03d}"
        else:
            work_dir = base_work_dir

        # 5. 处理覆盖模式
        if mode == "overwrite" and work_dir.exists():
            shutil.rmtree(work_dir)

        # 6. 创建目录
        work_dir.mkdir(parents=True, exist_ok=True)

        # 7. 写入元数据（如果文件不存在或模式为 overwrite）
        meta_path = work_dir / ".workdir_meta.json"
        if mode == "overwrite" or not meta_path.exists():
            meta = {
                "created_at": datetime.now().isoformat(),
                "formula": formula,
                "workflow_type": workflow_type.value,
                "structure_hash": struct_hash,
                "mode": mode,
            }
            meta_path.write_text(json.dumps(meta, indent=2))

        return work_dir

    def clean(self, work_dir: Path) -> None:
        """删除工作目录（清理磁盘空间）"""
        if work_dir.exists() and work_dir.is_dir():
            shutil.rmtree(work_dir)

    def get_meta(self, work_dir: Path) -> Optional[dict]:
        """读取工作目录的元数据"""
        meta_path = work_dir / ".workdir_meta.json"
        if meta_path.exists():
            return json.loads(meta_path.read_text())
        return None

    def list_workdirs(self, formula: Optional[str] = None, workflow_type: Optional[WorkflowType] = None) -> list:
        """列出所有工作目录"""
        results = []
        base = self.base_dir
        if formula:
            base = base / formula
        if workflow_type:
            base = base / workflow_type.value

        if not base.exists():
            return results

        for path in base.rglob(".workdir_meta.json"):
            meta = json.loads(path.read_text())
            results.append({
                "path": str(path.parent),
                "meta": meta,
            })
        return results