"""Calculator 公共辅助函数"""

import asyncio
from typing import Callable, TypeVar, Awaitable
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor
from ase import Atoms

T = TypeVar("T")


async def run_blocking(func: Callable[[], T]) -> T:
    """统一封装 run_in_executor，避免重复代码"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func)


def to_ase(structure: Structure) -> Atoms:
    """pymatgen Structure → ASE Atoms"""
    return AseAtomsAdaptor.get_atoms(structure)


def to_pmg(atoms: Atoms) -> Structure:
    """ASE Atoms → pymatgen Structure"""
    return AseAtomsAdaptor.get_structure(atoms)