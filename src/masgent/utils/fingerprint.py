"""Fingerprint 生成工具——用于缓存键和目录路径"""

import hashlib
import json
from pymatgen.core import Structure

from masgent.models.enums import WorkflowType


def structure_hash(structure: Structure) -> str:
    """生成结构的确定性哈希（SHA256）"""
    data = {
        "formula": structure.composition.reduced_formula,
        "lattice": structure.lattice.matrix.tolist(),
        "sites": [
            {
                "species": str(site.specie),
                "frac_coords": [round(x, 6) for x in site.frac_coords],
                "properties": site.properties if site.properties else {},
            }
            for site in structure.sites
        ],
    }
    if hasattr(structure, "charge") and structure.charge is not None:
        data["charge"] = structure.charge
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


def calculation_fingerprint(
    structure: Structure,
    workflow_type: WorkflowType,
    params: dict = None,
    calculator_type: str = "unknown",
) -> str:
    """生成计算指纹（用于缓存键）"""
    data = {
        "structure_hash": structure_hash(structure),
        "workflow_type": workflow_type.value,
        "calculator_type": calculator_type,
        "params": params or {},
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]