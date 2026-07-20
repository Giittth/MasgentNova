"""测试 masgent.tools 中的核心工具函数"""

import os
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from pymatgen.core import Structure, Lattice

import masgent.tools as tools
from masgent.models import schemas
from masgent._config import config


# list_files 测试
def test_list_files(tmp_path, monkeypatch):
    """测试 list_files 函数"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    # 创建一些文件
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.txt").write_text("content2")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("content3")

    result = tools.list_files()

    assert result["status"] == "success"
    assert len(result["files"]) == 3
    assert "file1.txt" in "".join(result["files"])
    assert "file2.txt" in "".join(result["files"])
    assert "file3.txt" in "".join(result["files"])


def test_list_files_empty(tmp_path, monkeypatch):
    """测试空目录"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    result = tools.list_files()
    assert result["status"] == "success"
    assert len(result["files"]) == 0


# read_file 测试
def test_read_file(tmp_path, monkeypatch):
    """测试 read_file 函数"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    file_path = tmp_path / "test.txt"
    content = "Hello, Masgent!"
    file_path.write_text(content)

    result = tools.read_file("test.txt")
    assert result["status"] == "success"
    assert result["content"] == content


def test_read_file_not_found(tmp_path, monkeypatch):
    """测试读取不存在的文件"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    result = tools.read_file("nonexistent.txt")
    assert result["status"] == "error"
    assert "error" in result["message"].lower()


# rename_file 测试
def test_rename_file(tmp_path, monkeypatch):
    """测试 rename_file 函数"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    file_path = tmp_path / "old_name.txt"
    file_path.write_text("content")

    result = tools.rename_file("old_name.txt", "new_name.txt")
    assert result["status"] == "success"

    # 验证新文件存在
    assert (tmp_path / "new_name.txt").exists()
    # 旧文件仍然存在（因为 copy2 是复制）
    assert (tmp_path / "old_name.txt").exists()


def test_rename_file_not_found(tmp_path, monkeypatch):
    """测试重命名不存在的文件"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    result = tools.rename_file("nonexistent.txt", "new_name.txt")
    assert result["status"] == "error"


def test_rename_file_outside_dir(tmp_path, monkeypatch):
    """测试重命名到目录外（应被阻止）"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    file_path = tmp_path / "test.txt"
    file_path.write_text("content")

    # 尝试移动到上级目录
    result = tools.rename_file("test.txt", "../outside.txt")
    assert result["status"] == "error"
    assert "outside" in result["message"] or "not allowed" in result["message"]


# convert_structure_format 测试
def test_convert_structure_format_poscar_to_cif(tmp_path, monkeypatch, poscar_nacl):
    """测试 POSCAR → CIF 转换"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    # 写入 POSCAR 文件
    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.convert_structure_format(
        input_path=str(poscar_path),
        input_format="POSCAR",
        output_format="CIF"
    )

    assert result["status"] == "success"
    # 验证输出文件存在
    convert_dir = tmp_path / "convert"
    assert (convert_dir / "POSCAR.cif").exists()


def test_convert_structure_format_invalid_input(tmp_path, monkeypatch):
    """测试无效的输入文件"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    invalid_path = tmp_path / "invalid.vasp"
    invalid_path.write_text("这不是结构文件")

    result = tools.convert_structure_format(
        input_path=str(invalid_path),
        input_format="POSCAR",
        output_format="CIF"
    )

    assert result["status"] == "error"


# convert_poscar_coordinates 测试
def test_convert_poscar_coordinates_to_cartesian(tmp_path, monkeypatch, poscar_nacl):
    """测试 POSCAR 坐标转换：Direct → Cartesian"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.convert_poscar_coordinates(
        poscar_path=str(poscar_path),
        to_cartesian=True
    )

    print("\n[DEBUG] convert_poscar_coordinates_to_cartesian result:", result)

    assert result["status"] == "success"
    convert_dir = tmp_path / "convert"
    assert (convert_dir / "POSCAR").exists()


def test_convert_poscar_coordinates_to_direct(tmp_path, monkeypatch, poscar_nacl):
    """测试 POSCAR 坐标转换：Cartesian → Direct"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.convert_poscar_coordinates(
        poscar_path=str(poscar_path),
        to_cartesian=False
    )

    print("\n[DEBUG] convert_poscar_coordinates_to_direct result:", result)

    assert result["status"] == "success"
    convert_dir = tmp_path / "convert"
    assert (convert_dir / "POSCAR").exists()


# customize_vasp_kpoints_with_accuracy 测试
def test_customize_kpoints_low_accuracy(tmp_path, monkeypatch, poscar_nacl):
    """测试 Low 精度 KPOINTS 生成"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.customize_vasp_kpoints_with_accuracy(
        poscar_path=str(poscar_path),
        accuracy_level="Low",
        gamma_centered=True
    )

    print("\n[DEBUG] customize_kpoints_low_accuracy result:", result)

    assert result["status"] == "success"
    assert (tmp_path / "KPOINTS").exists()
    content = (tmp_path / "KPOINTS").read_text()
    # Gamma-centered 应该包含 Gamma
    assert "Gamma" in content or "0.0" in content


def test_customize_kpoints_custom_kppa(tmp_path, monkeypatch, poscar_nacl):
    """测试 Custom 精度 KPOINTS 生成（自定义 kppa）"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.customize_vasp_kpoints_with_accuracy(
        poscar_path=str(poscar_path),
        accuracy_level="Custom",
        custom_kppa=2000,
        gamma_centered=False
    )

    print("\n[DEBUG] customize_kpoints_custom_kppa result:", result)

    assert result["status"] == "success"
    assert (tmp_path / "KPOINTS").exists()
    content = (tmp_path / "KPOINTS").read_text()
    # Monkhorst-Pack 不应该包含 Gamma
    assert "Gamma" not in content


# generate_supercell_from_poscar 测试
def test_generate_supercell_2x2x2(tmp_path, monkeypatch, poscar_nacl):
    """测试 2x2x2 超胞生成"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_supercell_from_poscar(
        poscar_path=str(poscar_path),
        scaling_matrix="2 0 0; 0 2 0; 0 0 2"
    )

    print("\n[DEBUG] generate_supercell_2x2x2 result:", result)

    assert result["status"] == "success"
    supercell_dir = tmp_path / "supercell"
    assert (supercell_dir / "POSCAR").exists()

    # 验证超胞原子数
    structure = Structure.from_file(supercell_dir / "POSCAR")
    # NaCl 原胞有 8 个原子，2x2x2 超胞应该有 8 * 8 = 64 个原子
    assert len(structure) == 64


def test_generate_supercell_invalid_matrix(tmp_path, monkeypatch, poscar_nacl):
    """测试非法的超胞矩阵"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_supercell_from_poscar(
        poscar_path=str(poscar_path),
        scaling_matrix="2 0; 0 2"
    )

    assert result["status"] == "error"
    assert "3x3" in result["message"] or "Invalid" in result["message"]


# generate_vasp_inputs_from_poscar 测试（需要 POTCAR 但可以不实际写入）
@patch('pymatgen.io.vasp.sets.MPRelaxSet')
def test_generate_vasp_inputs_only_incar(mock_relax_set, tmp_path, monkeypatch, poscar_nacl):
    """测试仅生成 INCAR（使用 Mock 避免 POTCAR 依赖）"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    # Mock MPRelaxSet
    mock_vis = MagicMock()
    mock_vis.incar = MagicMock()
    mock_vis.poscar = MagicMock()
    mock_relax_set.return_value = mock_vis

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_vasp_inputs_from_poscar(
        poscar_path=str(poscar_path),
        vasp_input_sets="MPRelaxSet",
        only_incar=True
    )

    print("\n[DEBUG] generate_vasp_inputs_only_incar result:", result)

    assert result["status"] == "success"
    assert "INCAR" in result["message"]


# generate_vasp_poscar 测试（需要 mock MP API）
@patch('masgent.tools.vasp.validate_mp_api_key')
@patch('masgent.tools.vasp.ask_for_mp_api_key')
@patch('mp_api.client.MPRester')
def test_generate_vasp_poscar_success(
    mock_mpr,
    mock_ask_key,
    mock_validate,
    tmp_path,
    monkeypatch,
    poscar_nacl
):
    """测试通过 MP API 生成 POSCAR（使用 Mock）"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))
    monkeypatch.setenv("MP_API_KEY", "fake_key")

    # 设置全局 _mp_key_checked = False（需要直接访问 tools.vasp 模块）
    import masgent.tools.vasp as vasp_module
    vasp_module._mp_key_checked = False

    # Mock MPRester
    mock_instance = MagicMock()
    mock_mpr.return_value.__enter__.return_value = mock_instance

    # Mock materials.summary.search 的返回值
    mock_doc = MagicMock()
    mock_doc.material_id = "mp-22862"
    mock_doc.energy_above_hull = 0.0
    mock_doc.symmetry.crystal_system = "Cubic"
    mock_doc.symmetry.symbol = "Fm-3m"
    mock_instance.materials.summary.search.return_value = [mock_doc]

    # Mock get_structure_by_material_id
    mock_instance.get_structure_by_material_id.return_value = poscar_nacl

    result = tools.generate_vasp_poscar(formula="NaCl")

    assert result["status"] == "success"
    assert "POSCAR" in result["message"]
    assert result["most_stable_poscar"] == os.path.join(tmp_path, "POSCAR_NaCl")


@patch('masgent.tools.vasp.validate_mp_api_key')
@patch('masgent.tools.vasp.ask_for_mp_api_key')
def test_generate_vasp_poscar_no_results(mock_ask, mock_validate, tmp_path, monkeypatch):
    """测试 MP API 返回空结果"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))
    monkeypatch.setenv("MP_API_KEY", "fake_key")

    mock_validate.return_value = None
    mock_ask.return_value = None

    with patch('mp_api.client.MPRester') as mock_mpr:
        mock_instance = MagicMock()
        mock_mpr.return_value.__enter__.return_value = mock_instance
        mock_instance.materials.summary.search.return_value = []

        import masgent.tools.vasp as vasp_module
        vasp_module._mp_key_checked = False

        result = tools.generate_vasp_poscar(formula="NaCl")

        assert result["status"] == "error"
        assert "No materials found" in result["message"]


# generate_vasp_poscar_with_vacancy_defects 测试
def test_generate_vacancy_defects(tmp_path, monkeypatch, poscar_nacl):
    """测试空位缺陷生成"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_vasp_poscar_with_vacancy_defects(
        poscar_path=str(poscar_path),
        original_element="Na",
        defect_amount=0.25
    )

    assert result["status"] == "success"
    defect_dir = tmp_path / "defects" / "vacancies"
    assert (defect_dir / "POSCAR").exists()

    # 验证原子数减少
    new_structure = Structure.from_file(defect_dir / "POSCAR")
    # 原 8 个原子，其中 4 个 Na。移除 25% 即移除 1 个 Na，应剩 7 个原子
    assert len(new_structure) == 7


def test_generate_vacancy_defects_invalid_element(tmp_path, monkeypatch, poscar_nacl):
    """测试非法元素应返回错误"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_vasp_poscar_with_vacancy_defects(
        poscar_path=str(poscar_path),
        original_element="Xy",
        defect_amount=0.25
    )

    assert result["status"] == "error"


# generate_vasp_poscar_with_substitution_defects 测试
def test_generate_substitution_defects(tmp_path, monkeypatch, poscar_nacl):
    """测试替代缺陷生成"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_vasp_poscar_with_substitution_defects(
        poscar_path=str(poscar_path),
        original_element="Na",
        defect_element="K",
        defect_amount=0.25
    )

    assert result["status"] == "success"
    defect_dir = tmp_path / "defects" / "substitutions"
    assert (defect_dir / "POSCAR").exists()

    # 验证 K 原子存在
    new_structure = Structure.from_file(defect_dir / "POSCAR")
    symbols = [str(site.specie) for site in new_structure]
    assert "K" in symbols


# generate_vasp_poscar_with_interstitial_defects 测试
def test_generate_interstitial_defects(tmp_path, monkeypatch, poscar_nacl):
    """测试间隙缺陷生成（Voronoi）"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_vasp_poscar_with_interstitial_defects(
        poscar_path=str(poscar_path),
        defect_element="Li"
    )

    print("\n[DEBUG] interstitial result:", result)

    if result["status"] == "error" and "no interstitial" in result["message"].lower():
        assert True
    else:
        assert result["status"] == "success"


# generate_surface_slab_from_poscar 测试
def test_generate_surface_slab(tmp_path, monkeypatch, poscar_nacl):
    """测试表面 slab 生成"""
    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))

    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_surface_slab_from_poscar(
        poscar_path=str(poscar_path),
        miller_indices=[1, 0, 0],
        vacuum_thickness=15.0,
        slab_layers=4
    )

    assert result["status"] == "success"
    slab_dir = tmp_path / "surface_slab"
    assert (slab_dir / "POSCAR").exists()


# generate_vasp_workflow_of_eos 测试
@patch('masgent.tools.vasp.write_comments')
@patch('masgent.tools.vasp.MPStaticSet')
def test_generate_eos_workflow(mock_mpss, mock_write_comments, tmp_path, monkeypatch, poscar_nacl):
    """测试 EOS 工作流生成（只验证目录结构）"""
    mock_vis = MagicMock()
    mock_vis.incar = MagicMock()
    mock_vis.kpoints = MagicMock()
    mock_vis.potcar = MagicMock()
    mock_vis.poscar = MagicMock()
    mock_mpss.return_value = mock_vis
    mock_write_comments.return_value = None

    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))
    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_vasp_workflow_of_eos(
        poscar_path=str(poscar_path),
        scale_factors=[0.95, 1.00, 1.05]
    )

    print("\n[DEBUG] generate_eos_workflow result:", result)

    assert result["status"] == "success"
    eos_dir = tmp_path / "eos_calculations"
    assert eos_dir.exists()
    scale_dirs = [d for d in eos_dir.iterdir() if d.is_dir() and d.name.startswith("scale_")]
    assert len(scale_dirs) == 3


# generate_vasp_workflow_of_elastic_constants 测试
@patch('masgent.tools.vasp.write_comments')
@patch('masgent.tools.vasp.MPStaticSet')
def test_generate_elastic_workflow(mock_mpss, mock_write_comments, tmp_path, monkeypatch, poscar_nacl):
    """测试弹性常数工作流生成（只验证目录结构）"""
    mock_vis = MagicMock()
    mock_vis.incar = MagicMock()
    mock_vis.kpoints = MagicMock()
    mock_vis.potcar = MagicMock()
    mock_vis.poscar = MagicMock()
    mock_mpss.return_value = mock_vis
    mock_write_comments.return_value = None

    monkeypatch.setattr(config, 'runs_dir', str(tmp_path))
    poscar_path = tmp_path / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")

    result = tools.generate_vasp_workflow_of_elastic_constants(
        poscar_path=str(poscar_path)
    )

    assert result["status"] == "success"
    elastic_dir = tmp_path / "elastic_constants"
    assert elastic_dir.exists()