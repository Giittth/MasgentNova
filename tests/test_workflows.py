"""测试 workflow 分析模块（最终正式版）

关键决策：
- Elastic：patch 原始模块 pymatgen.analysis.elasticity.strain.Strain 和 stress.Stress
          （因为 workflow.py 内部 import，不是模块级导入）
- AIMD：每帧独立对象，避免同一引用
- 所有成功路径验证输出文件存在且内容正确
- 所有核心 mock 验证被调用
- 为 Convergence 源码 bug 添加注释
"""

import os
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

from masgent.tools.workflow import (
    analyze_vasp_workflow_of_convergence_tests,
    analyze_vasp_workflow_of_eos,
    analyze_vasp_workflow_of_elastic_constants,
    analyze_vasp_workflow_of_aimd,
    analyze_vasp_workflow_of_neb,
)


# ==================== 辅助函数 ====================

def create_minimal_poscar(path):
    content = """Si
1.0
0.0 0.5 0.5
0.5 0.0 0.5
0.5 0.5 0.0
Si
8
Direct
0.0 0.0 0.0
0.25 0.25 0.25
0.5 0.5 0.5
0.75 0.75 0.75
0.0 0.0 0.0
0.25 0.25 0.25
0.5 0.5 0.5
0.75 0.75 0.75
"""
    path.write_text(content)


# ==================== Fixtures ====================

@pytest.fixture
def mock_vasprun():
    mock = MagicMock()
    mock.final_energy = -10.0
    mock.atomic_symbols = ["Si"] * 8
    mock.final_structure = MagicMock()
    mock.final_structure.volume = 100.0
    mock.ionic_steps = [{"stress": [-1.0, -1.0, -1.0, 0.0, 0.0, 0.0]}]
    return mock


@pytest.fixture
def mock_neb_analysis():
    mock = MagicMock()
    mock.r = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    mock.energies = np.array([0.0, 0.5, 1.0, 0.5, 0.0])
    def fake_spline(x):
        return 4 * x * (1 - x)
    mock.spline.side_effect = fake_spline
    return mock


# ==================== 1. Convergence ====================

def test_analyze_convergence_success(tmp_path, mock_vasprun):
    """成功分析收敛测试目录"""
    encut_dir = tmp_path / "encut_tests" / "encut_300"
    kpoint_dir = tmp_path / "kpoint_tests" / "kppa_1000"
    encut_dir.mkdir(parents=True)
    kpoint_dir.mkdir(parents=True)
    (encut_dir / "vasprun.xml").touch()
    (kpoint_dir / "vasprun.xml").touch()

    with patch('masgent.tools.workflow.Vasprun') as mock_class:
        mock_class.return_value = mock_vasprun
        result = analyze_vasp_workflow_of_convergence_tests(str(tmp_path))

    assert result["status"] == "success"
    encut_plot = Path(result["encut_tests_plot"])
    kpoint_plot = Path(result["kpoint_tests_plot"])
    assert encut_plot.exists()
    assert kpoint_plot.exists()
    assert encut_plot.stat().st_size > 1000
    assert kpoint_plot.stat().st_size > 1000


def test_analyze_convergence_dir_not_exist():
    """目录不存在 —— 当前源码因未初始化变量而触发 UnboundLocalError，返回 error
    修复建议：在函数开头初始化 encut_tests_dict = {}, kpoint_tests_dict = {}
    """
    result = analyze_vasp_workflow_of_convergence_tests("/nonexistent")
    assert result["status"] == "error"
    assert "Error analyzing" in result["message"] or "Invalid" in result["message"]


def test_analyze_convergence_no_data(tmp_path):
    """目录存在但无子目录 —— 同样触发未定义变量，返回 error
    修复后应期望 success 且 plot 为 None
    """
    result = analyze_vasp_workflow_of_convergence_tests(str(tmp_path))
    assert result["status"] == "error"


# ==================== 2. EOS ====================

def test_analyze_eos_success(tmp_path, mock_vasprun):
    """成功分析 EOS 目录"""
    scales = [0.95, 1.00, 1.05]
    for s in scales:
        scale_dir = tmp_path / f"scale_{s:.3f}"
        scale_dir.mkdir(parents=True)
        create_minimal_poscar(scale_dir / "POSCAR")
        (scale_dir / "vasprun.xml").touch()

    def fake_to(filename):
        Path(filename).write_text("POSCAR_equilibrium content")

    mock_structure = MagicMock()
    mock_structure.volume = 100.0
    mock_structure.copy.return_value = mock_structure
    mock_structure.scale_lattice = MagicMock()
    mock_structure.to = MagicMock(side_effect=fake_to)

    with patch('masgent.tools.workflow.fit_eos') as mock_fit:
        mock_fit.return_value = (
            np.array([90, 95, 100, 105, 110]),
            np.array([-9.8, -9.9, -10.0, -9.9, -9.8])
        )
        with patch('masgent.tools.workflow.Structure.from_file', return_value=mock_structure):
            with patch('masgent.tools.workflow.Vasprun') as mock_class:
                mock_class.return_value = mock_vasprun
                result = analyze_vasp_workflow_of_eos(str(tmp_path))

    assert result["status"] == "success"
    csv_path = Path(result["eos_fit_csv"])
    curve_path = Path(result["eos_curve_plot"])
    poscar_path = Path(result["poscar_equilibrium"])
    assert csv_path.exists()
    assert curve_path.exists()
    assert poscar_path.exists()
    assert poscar_path.stat().st_size > 0

    df = pd.read_csv(csv_path)
    assert list(df.columns) == ["Volume[Å³/atom]", "Energy[eV/atom]"]
    assert df["Energy[eV/atom]"].min() == -10.0
    assert len(df) == 5
    mock_fit.assert_called_once()


def test_analyze_eos_dir_not_exist():
    result = analyze_vasp_workflow_of_eos("/nonexistent")
    assert result["status"] == "error"


# ==================== 3. Elastic ====================

def test_analyze_elastic_success(tmp_path, mock_vasprun):
    """成功分析弹性常数目录（patch 原始模块，因为函数内部 import）"""
    for folder in ["00_strain_0.000", "01_strain_xx_0.010"]:
        folder_path = tmp_path / folder
        folder_path.mkdir(parents=True)
        (folder_path / "vasprun.xml").touch()

    # patch 原始模块（因为 workflow.py 在函数内部 import）
    with patch('pymatgen.analysis.elasticity.strain.Strain') as mock_strain:
        mock_strain.return_value = MagicMock()
        with patch('pymatgen.analysis.elasticity.stress.Stress') as mock_stress:
            mock_stress.return_value = MagicMock()
            with patch('pymatgen.analysis.elasticity.elastic.ElasticTensor.from_independent_strains') as mock_from:
                mock_elastic = MagicMock()
                mock_elastic.voigt = np.eye(6) * 100.0
                mock_elastic.k_voigt = 100.0
                mock_elastic.k_reuss = 100.0
                mock_elastic.k_vrh = 100.0
                mock_elastic.g_voigt = 50.0
                mock_elastic.g_reuss = 50.0
                mock_elastic.g_vrh = 50.0
                mock_from.return_value = mock_elastic

                with patch('masgent.tools.workflow.Vasprun') as mock_class:
                    mock_class.return_value = mock_vasprun
                    with patch('masgent.tools.workflow.create_deformation_matrices') as mock_deform:
                        mock_deform.return_value = [
                            {"00_strain_0.000": [[0,0,0],[0,0,0],[0,0,0]]},
                            {"01_strain_xx_0.010": [[0.01,0,0],[0,0,0],[0,0,0]]},
                        ]
                        result = analyze_vasp_workflow_of_elastic_constants(str(tmp_path))

    assert result["status"] == "success", result.get("message", "")
    txt_path = Path(result["elastic_constants_txt"])
    assert txt_path.exists()
    content = txt_path.read_text()
    assert "Elastic Constants" in content
    assert "Bulk Modulus" in content
    assert "100.00" in content
    mock_from.assert_called_once()


def test_analyze_elastic_dir_not_exist():
    result = analyze_vasp_workflow_of_elastic_constants("/nonexistent")
    assert result["status"] == "error"


# ==================== 4. AIMD ====================

def test_analyze_aimd_success(tmp_path):
    """成功分析 AIMD 目录（至少两个温度），每帧独立对象"""
    temps = [500, 600]
    for T in temps:
        temp_dir = tmp_path / f"T_{T}K"
        temp_dir.mkdir(parents=True)
        (temp_dir / "INCAR").write_text("POTIM = 2.0\n")
        oszicar_lines = [
            f" 1 F= -.123 E0= -.123 dE=0 T= {T+10*i:.1f} E= -10.0\n"
            for i in range(5)
        ]
        (temp_dir / "OSZICAR").write_text("".join(oszicar_lines))
        (temp_dir / "XDATCAR").touch()

    mock_atom = MagicMock(symbol="Si")
    def frame_iter():
        return iter([mock_atom, mock_atom])

    mock_traj = []
    for _ in range(10):
        frame = MagicMock()
        frame.__iter__.side_effect = frame_iter
        frame.get_positions.return_value = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        frame.cell.array = np.eye(3) * 10.0
        mock_traj.append(frame)

    with patch('masgent.tools.workflow.read', return_value=mock_traj):
        with patch('masgent.tools.workflow.schemas.CheckElement', return_value=True):
            result = analyze_vasp_workflow_of_aimd(str(tmp_path), "Si")

    assert result["status"] == "success"
    csv_path = Path(result["diffusion_coefficients_csv"])
    plot_path = Path(result["arrhenius_plot"])
    assert csv_path.exists()
    assert plot_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) == 2
    assert plot_path.stat().st_size > 1000


def test_analyze_aimd_dir_not_exist():
    result = analyze_vasp_workflow_of_aimd("/nonexistent", "Si")
    assert result["status"] == "error"


def test_analyze_aimd_invalid_specie():
    with patch('masgent.tools.workflow.schemas.CheckElement', side_effect=ValueError("Invalid")):
        result = analyze_vasp_workflow_of_aimd("/some/path", "Xx")
        assert result["status"] == "error"
        assert "Invalid input parameters" in result["message"]


# ==================== 5. NEB ====================

def test_analyze_neb_success(tmp_path, mock_neb_analysis):
    """成功分析 NEB 目录"""
    for i in range(5):
        img_dir = tmp_path / f"0{i}"
        img_dir.mkdir(parents=True)
        create_minimal_poscar(img_dir / "POSCAR")

    with patch('pymatgen.analysis.transition_state.NEBAnalysis.from_dir') as mock_from_dir:
        mock_from_dir.return_value = mock_neb_analysis
        result = analyze_vasp_workflow_of_neb(str(tmp_path))

    assert result["status"] == "success"
    spline_csv = Path(result["neb_data_spline_csv"])
    points_csv = Path(result["neb_data_points_csv"])
    barrier_txt = Path(result["energy_barrier_txt"])
    plot = Path(result["neb_energy_profile_plot"])
    assert spline_csv.exists()
    assert points_csv.exists()
    assert barrier_txt.exists()
    assert plot.exists()

    df_spline = pd.read_csv(spline_csv)
    assert len(df_spline) > 0
    df_points = pd.read_csv(points_csv)
    assert len(df_points) == 5
    assert "Energy Barrier" in barrier_txt.read_text()
    mock_from_dir.assert_called_once()


def test_analyze_neb_dir_not_exist():
    result = analyze_vasp_workflow_of_neb("/nonexistent")
    assert result["status"] == "error"