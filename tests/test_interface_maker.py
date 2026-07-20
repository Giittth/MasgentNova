"""测试 masgent/utils/interface_maker.py 中的核心逻辑"""

import os
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from pymatgen.core import Structure, Lattice

import masgent.utils.interface_maker as im


# reduce 函数测试
def test_reduce_basic():
    """测试基本的晶格矢量约化"""
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    a_list, b_list, T_list = im.reduce(a, b)
    a_final, b_final = a_list[-1], b_list[-1]
    assert np.linalg.norm(a_final) <= np.linalg.norm(a)
    assert np.linalg.norm(b_final) <= np.linalg.norm(b)
    assert np.allclose(T_list[-1], np.eye(2))


def test_reduce_oblique():
    """测试斜晶格的约化"""
    a = np.array([2.0, 0.0])
    b = np.array([1.0, 1.0])
    a_list, b_list, T_list = im.reduce(a, b)
    a_final, b_final = a_list[-1], b_list[-1]
    assert np.linalg.norm(a_final) <= np.linalg.norm(a)
    assert np.linalg.norm(b_final) <= np.linalg.norm(b)


def test_find_int():
    """测试整数近似查找"""
    area_0 = 10.0
    area_1 = 20.0
    area = 100.0
    int_list, ratio = im.find_int(area_0, area_1, area)
    assert len(int_list) > 0
    assert ratio == area_0 / area_1
    assert int_list[0] == [1, 1, 1]


def test_find_ijm():
    """测试 ijm 列表生成"""
    N = 4
    ijm_list = im.find_ijm(N)
    expected = [
        [1, 0, 4], [1, 1, 4], [1, 2, 4], [1, 3, 4],
        [2, 0, 2], [2, 1, 2],
        [4, 0, 1]
    ]
    assert len(ijm_list) == len(expected)
    for item in expected:
        assert item in ijm_list


def test_cal_mis():
    """测试失配计算"""
    u_mis, v_mis, angle_mis = im.cal_mis(1.0, 2.0, 90.0, 1.0, 2.0, 90.0)
    assert u_mis == 0.0
    assert v_mis == 0.0
    assert angle_mis == 0.0

    u_mis, v_mis, angle_mis = im.cal_mis(1.0, 2.0, 90.0, 1.1, 2.1, 89.0)
    assert u_mis == pytest.approx(0.1)
    assert v_mis == pytest.approx(0.05)
    assert angle_mis == 1.0


def test_trim():
    """测试数据去重"""
    data = [
        [1, 2, 3, 3, 4, 5],
        [6, 7, 8, 3, 4, 5],
        [9, 10, 11, 1, 2, 3],
    ]
    trimmed, same_idx = im.trim(data)
    assert len(trimmed) == 2
    assert 1 in same_idx


@patch('masgent.utils.interface_maker.read')
@patch('masgent.utils.interface_maker.write')
@patch('masgent.utils.interface_maker.surface')
def test_slab_maker(mock_surface, mock_write, mock_read, tmp_path):
    """测试 slab_maker 函数"""
    im.OUTPUT_DIR = str(tmp_path)

    mock_atom = MagicMock()
    mock_read.return_value = mock_atom

    mock_slab1 = MagicMock()
    mock_slab1.cell = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    mock_slab2 = MagicMock()
    mock_slab2.cell = np.array([[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]])
    mock_surface.side_effect = [mock_slab1, mock_slab2]

    cell_conv = "dummy.vasp"
    miller_indices = [(1, 0, 0), (1, 1, 1)]
    vacuum = 10.0
    layers = 3
    data = im.slab_maker(cell_conv, miller_indices, vacuum, layers)

    assert len(data) == len(miller_indices)
    assert data[0][0] == "100"
    assert mock_write.call_count == len(miller_indices)


def test_pair_slabs():
    """测试 slab 配对"""
    data_lower = [["100", 10.0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]
    data_upper = [["111", 20.0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]
    area = 100.0
    pairs = im.pair_slabs(data_lower, data_upper, area)
    assert len(pairs) == 1
    assert pairs[0][0] == "100"
    assert pairs[0][1] == "111"


def test_cal_uv():
    """测试超胞矢量计算"""
    data_slab = [["100", 10.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 90.0]]
    hkl = "100"
    n = 4
    uv_data = im.cal_uv(data_slab, hkl, n)
    assert len(uv_data) > 0
    assert uv_data[0][0] == hkl


def test_lattice_match():
    """测试晶格匹配主逻辑"""
    data_pairs = [
        ["100", "111", 10.0, 20.0, 0.5, [[1, 1, 1], [2, 1, 2]]]
    ]
    data_ab_lower = [["100", 10.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 90.0]]
    data_ab_upper = [["111", 20.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 90.0]]

    im.UV_TOL = 5.0
    im.ANGLE_TOL = 5.0

    matched = im.lattice_match(data_pairs, data_ab_lower, data_ab_upper)
    assert isinstance(matched, list)


def test_filter_data():
    """测试数据过滤"""
    data_matched = [
        ["100", "111", 0.01, 0.01, 0.1, 50.0, 60.0,
         1, 0, 0, 1, 1, 0, 0, 1, 1.0, 1.0, 90.0, 1.0, 1.0, 90.0],
        ["100", "111", 0.02, 0.02, 0.2, 50.0, 60.0,
         1, 0, 0, 1, 1, 0, 0, 1, 1.5, 1.5, 90.0, 1.5, 1.5, 90.0],
    ]
    im.SHAPE_FILTER = False
    filtered, min_area = im.filter_data(data_matched, 50.0)
    assert len(filtered) == len(data_matched)

    im.SHAPE_FILTER = True
    filtered2, min_area2 = im.filter_data(data_matched, 50.0)
    assert len(filtered2) == 1


@patch('masgent.utils.interface_maker.slab_maker')
@patch('masgent.utils.interface_maker.pair_slabs')
@patch('masgent.utils.interface_maker.lattice_match')
@patch('masgent.utils.interface_maker.filter_data')
@patch('masgent.utils.interface_maker.gen_intf')
@patch('shutil.rmtree')
def test_run_interface_maker(
    mock_rmtree, mock_gen_intf, mock_filter_data,
    mock_lattice_match, mock_pair_slabs, mock_slab_maker,
    tmp_path
):
    """测试 run_interface_maker 主流程（使用真实文件系统）"""
    output_dir = tmp_path / "interfaces"

    mock_slab_maker.side_effect = [
        [["100", 10.0, 1, 2, 3, 4, 5, 6, 7, 8, 9]],
        [["111", 20.0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]
    ]
    mock_pair_slabs.return_value = [["100", "111", 10.0, 20.0, 0.5, [[1, 1, 1]]]]
    mock_lattice_match.return_value = [
        ["100", "111", 0.01, 0.01, 0.1, 50.0, 60.0,
         1, 0, 0, 1, 1, 0, 0, 1, 1.0, 1.0, 90.0, 1.0, 1.0, 90.0]
    ]
    mock_filter_data.return_value = (
        [["100", "111", 0.01, 0.01, 0.1, 50.0, 60.0,
          1, 0, 0, 1, 1, 0, 0, 1, 1.0, 1.0, 90.0, 1.0, 1.0, 90.0]],
        50.0
    )

    im.run_interface_maker(
        lower_conv="lower.vasp",
        upper_conv="upper.vasp",
        lower_hkl=[1, 0, 0],
        upper_hkl=[1, 1, 1],
        min_area=50.0,
        max_area=100.0,
        slab_vacuum=10.0,
        interface_gap=2.0,
        lower_slab_layers=4,
        upper_slab_layers=4,
        uv_tol=5.0,
        angle_tol=5.0,
        shape_filter=False,
        output_dir=str(output_dir)
    )

    assert mock_gen_intf.call_count > 0
    log_file = output_dir / "interface_maker.log"
    assert log_file.exists()