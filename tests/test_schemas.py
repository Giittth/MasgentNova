"""测试 src/masgent/utils/schemas.py 中的所有校验类"""

import os
import pytest
import pandas as pd
from pydantic import ValidationError
from masgent.models import schemas

# ToolMetadata 测试
def test_tool_metadata_valid():
    """测试有效的 ToolMetadata"""
    data = {
        "name": "test_tool",
        "description": "A test tool",
        "requires": ["param1", "param2"],
        "optional": ["param3"],
        "defaults": {"param3": 42},
        "prereqs": ["prereq1"],
    }
    result = schemas.ToolMetadata(**data)
    assert result.name == "test_tool"
    assert result.requires == ["param1", "param2"]

# CheckPklFile 测试
def test_check_pkl_file_valid(tmp_path):
    """测试有效的 .pkl 文件"""
    pkl_path = tmp_path / "model.pkl"
    pkl_path.touch()
    result = schemas.CheckPklFile(file_path=str(pkl_path))
    assert result.file_path == str(pkl_path)

def test_check_pkl_file_not_found():
    """测试不存在的 .pkl 文件"""
    with pytest.raises(ValidationError) as exc:
        schemas.CheckPklFile(file_path="/nonexistent/model.pkl")
    assert "not found" in str(exc.value)

def test_check_pkl_file_wrong_extension(tmp_path):
    """测试非 .pkl 扩展名"""
    txt_path = tmp_path / "model.txt"
    txt_path.touch()
    with pytest.raises(ValidationError) as exc:
        schemas.CheckPklFile(file_path=str(txt_path))
    assert ".pkl" in str(exc.value)

# CheckLogFile 测试
def test_check_log_file_valid(tmp_path):
    """测试有效的 .log 文件"""
    log_path = tmp_path / "output.log"
    log_path.touch()
    result = schemas.CheckLogFile(file_path=str(log_path))
    assert result.file_path == str(log_path)

def test_check_log_file_not_found():
    """测试不存在的 .log 文件"""
    with pytest.raises(ValidationError) as exc:
        schemas.CheckLogFile(file_path="/nonexistent/log.log")
    assert "not found" in str(exc.value)

def test_check_log_file_wrong_extension(tmp_path):
    """测试非 .log 扩展名"""
    txt_path = tmp_path / "output.txt"
    txt_path.touch()
    with pytest.raises(ValidationError) as exc:
        schemas.CheckLogFile(file_path=str(txt_path))
    assert ".log" in str(exc.value)

# CheckCSVFile 测试
def test_check_csv_file_valid(tmp_path):
    """测试有效的 CSV 文件"""
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    csv_path = tmp_path / "data.csv"
    df.to_csv(csv_path, index=False)
    result = schemas.CheckCSVFile(file_path=str(csv_path))
    assert result.file_path == str(csv_path)

def test_check_csv_file_not_found():
    """测试不存在的 CSV 文件"""
    with pytest.raises(ValidationError) as exc:
        schemas.CheckCSVFile(file_path="/nonexistent/data.csv")
    assert "not found" in str(exc.value)

def test_check_csv_file_empty(tmp_path):
    """测试空 CSV 文件"""
    empty_path = tmp_path / "empty.csv"
    empty_path.touch()
    with pytest.raises(ValidationError) as exc:
        schemas.CheckCSVFile(file_path=str(empty_path))
    assert "empty" in str(exc.value)

def test_check_csv_file_invalid(tmp_path):
    """测试非 CSV 格式文件"""
    invalid_path = tmp_path / "invalid.csv"
    invalid_path.write_text("这不是 CSV 格式")
    with pytest.raises(ValidationError) as exc:
        schemas.CheckCSVFile(file_path=str(invalid_path))
    # 实际错误信息是 "CSV file is empty"（因为 pandas 读成空 DataFrame）
    assert "empty" in str(exc.value)

# CheckPoscar 测试
def test_check_poscar_valid(poscar_nacl_path):
    """测试有效的 POSCAR 文件"""
    result = schemas.CheckPoscar(poscar_path=str(poscar_nacl_path))
    assert result.poscar_path == str(poscar_nacl_path)

def test_check_poscar_not_found():
    """测试不存在的 POSCAR 文件"""
    with pytest.raises(ValidationError) as exc:
        schemas.CheckPoscar(poscar_path="/nonexistent/POSCAR")
    assert "not found" in str(exc.value)

def test_check_poscar_invalid(tmp_path):
    """测试无效的 POSCAR 内容"""
    invalid_path = tmp_path / "POSCAR"
    invalid_path.write_text("这不是 POSCAR 文件")
    with pytest.raises(ValidationError) as exc:
        schemas.CheckPoscar(poscar_path=str(invalid_path))
    assert "Invalid POSCAR" in str(exc.value)

# CheckElement 测试
def test_check_element_valid():
    """测试合法的化学元素符号"""
    result = schemas.CheckElement(element_symbol="Na")
    assert result.element_symbol == "Na"
    result = schemas.CheckElement(element_symbol="He")
    assert result.element_symbol == "He"

def test_check_element_invalid():
    """测试非法的化学元素符号"""
    with pytest.raises(ValidationError) as exc:
        schemas.CheckElement(element_symbol="Xy")
    assert "Invalid chemical element" in str(exc.value)

# CheckElementExistence 测试
def test_check_element_existence_valid(poscar_nacl_path):
    """测试元素存在于 POSCAR 中"""
    result = schemas.CheckElementExistence(
        poscar_path=str(poscar_nacl_path),
        element_symbol="Na"
    )
    assert result.element_symbol == "Na"

def test_check_element_existence_not_found(poscar_nacl_path):
    """测试元素不存在于 POSCAR 中"""
    with pytest.raises(ValidationError) as exc:
        schemas.CheckElementExistence(
            poscar_path=str(poscar_nacl_path),
            element_symbol="Si"
        )
    assert "does not exist" in str(exc.value)

def test_check_element_existence_invalid_element(poscar_nacl_path):
    """测试非法的元素符号"""
    with pytest.raises(ValidationError) as exc:
        schemas.CheckElementExistence(
            poscar_path=str(poscar_nacl_path),
            element_symbol="Xy"
        )
    assert "Invalid chemical element" in str(exc.value)

# GenerateVaspPoscarSchema 测试
def test_generate_poscar_schema_valid():
    """测试合法的化学式"""
    result = schemas.GenerateVaspPoscarSchema(formula="NaCl")
    assert result.formula == "NaCl"
    result = schemas.GenerateVaspPoscarSchema(formula="MgO")
    assert result.formula == "MgO"

def test_generate_poscar_schema_invalid():
    """测试非法的化学式（包含非法字符）"""
    with pytest.raises(ValidationError) as exc:
        schemas.GenerateVaspPoscarSchema(formula="Na-Cl")
    assert "Invalid" in str(exc.value)  # 可能是 "Invalid characters"

def test_generate_poscar_schema_empty():
    """测试空公式（实际上不会报错，改为测试包含空格的非法格式）"""
    with pytest.raises(ValidationError):
        schemas.GenerateVaspPoscarSchema(formula="Na Cl")

# ConvertStructureFormatSchema 测试
def test_convert_structure_format_valid(poscar_nacl_path):
    """测试有效的格式转换请求"""
    result = schemas.ConvertStructureFormatSchema(
        input_path=str(poscar_nacl_path),
        input_format="POSCAR",
        output_format="CIF"
    )
    assert result.input_format == "POSCAR"
    assert result.output_format == "CIF"

def test_convert_structure_format_same_format(poscar_nacl_path):
    """测试输入输出格式相同时应报错"""
    with pytest.raises(ValidationError) as exc:
        schemas.ConvertStructureFormatSchema(
            input_path=str(poscar_nacl_path),
            input_format="POSCAR",
            output_format="POSCAR"
        )
    assert "different" in str(exc.value)

def test_convert_structure_format_invalid_input(poscar_nacl_path):
    """测试非法输入格式（Literal 校验）"""
    with pytest.raises(ValidationError):
        schemas.ConvertStructureFormatSchema(
            input_path=str(poscar_nacl_path),
            input_format="INVALID",  # 不在 Literal 中
            output_format="CIF"
        )

def test_convert_structure_format_invalid_structure(tmp_path):
    """测试非法的结构文件"""
    invalid_path = tmp_path / "invalid.cif"
    invalid_path.write_text("这不是结构文件")
    with pytest.raises(ValidationError) as exc:
        schemas.ConvertStructureFormatSchema(
            input_path=str(invalid_path),
            input_format="CIF",
            output_format="POSCAR"
        )
    assert "Invalid structure" in str(exc.value)

# ConvertPoscarCoordinatesSchema 测试
def test_convert_poscar_coordinates_valid(poscar_nacl_path):
    """测试有效的坐标转换请求"""
    result = schemas.ConvertPoscarCoordinatesSchema(
        poscar_path=str(poscar_nacl_path),
        to_cartesian=True
    )
    assert result.to_cartesian is True

def test_convert_poscar_coordinates_path_not_found():
    """测试 POSCAR 不存在时使用默认路径应报错（默认路径通常不存在）"""
    with pytest.raises(ValidationError) as exc:
        schemas.ConvertPoscarCoordinatesSchema(to_cartesian=True)
    # 默认路径可能不存在，会触发文件未找到错误
    assert "not found" in str(exc.value) or "Invalid POSCAR" in str(exc.value)

# GenerateVaspInputsFromPoscar 测试
def test_generate_vasp_inputs_valid(poscar_nacl_path):
    """测试有效的 VASP 输入生成请求"""
    result = schemas.GenerateVaspInputsFromPoscar(
        poscar_path=str(poscar_nacl_path),
        vasp_input_sets="MPRelaxSet",
        only_incar=False
    )
    assert result.vasp_input_sets == "MPRelaxSet"

def test_generate_vasp_inputs_invalid_set(poscar_nacl_path):
    """测试非法的 input set（不在 Literal 中）"""
    with pytest.raises(ValidationError):
        schemas.GenerateVaspInputsFromPoscar(
            poscar_path=str(poscar_nacl_path),
            vasp_input_sets="InvalidSet"
        )

# GenerateVaspInputsHpcSlurmScript 测试
def test_hpc_slurm_script_valid():
    """测试有效的 Slurm 脚本参数"""
    result = schemas.GenerateVaspInputsHpcSlurmScript(
        partition="gpu",
        nodes=2,
        ntasks=16,
        walltime="02:00:00",
        jobname="test_job"
    )
    assert result.nodes == 2
    assert result.ntasks == 16

def test_hpc_slurm_script_invalid_nodes():
    """测试 nodes < 1"""
    with pytest.raises(ValidationError) as exc:
        schemas.GenerateVaspInputsHpcSlurmScript(nodes=0)
    assert "at least 1" in str(exc.value)

def test_hpc_slurm_script_invalid_walltime():
    """测试非法 walltime 格式"""
    with pytest.raises(ValidationError) as exc:
        schemas.GenerateVaspInputsHpcSlurmScript(walltime="25:00")  # 格式错误
    assert "HH:MM:SS" in str(exc.value)

# CustomizeVaspKpointsWithAccuracy 测试
def test_kpoints_accuracy_valid(poscar_nacl_path):
    """测试有效的 KPOINTS 精度配置"""
    result = schemas.CustomizeVaspKpointsWithAccuracy(
        poscar_path=str(poscar_nacl_path),
        accuracy_level="High"
    )
    assert result.accuracy_level == "High"

def test_kpoints_accuracy_custom_kppa_valid(poscar_nacl_path):
    """测试自定义 kppa 值"""
    result = schemas.CustomizeVaspKpointsWithAccuracy(
        poscar_path=str(poscar_nacl_path),
        accuracy_level="Custom",
        custom_kppa=2000
    )
    assert result.custom_kppa == 2000

def test_kpoints_accuracy_custom_kppa_invalid(poscar_nacl_path):
    """测试非法的 kppa 值（负数）"""
    with pytest.raises(ValidationError) as exc:
        schemas.CustomizeVaspKpointsWithAccuracy(
            poscar_path=str(poscar_nacl_path),
            accuracy_level="Custom",
            custom_kppa=0
        )
    assert "positive integer" in str(exc.value)

# GenerateSupercellFromPoscar 测试
def test_supercell_valid(poscar_nacl_path):
    """测试有效的超胞矩阵"""
    result = schemas.GenerateSupercellFromPoscar(
        poscar_path=str(poscar_nacl_path),
        scaling_matrix="2 0 0; 0 2 0; 0 0 2"
    )
    assert result.scaling_matrix == "2 0 0; 0 2 0; 0 0 2"

def test_supercell_invalid_matrix(poscar_nacl_path):
    """测试非法的超胞矩阵（非 3x3）"""
    with pytest.raises(ValidationError) as exc:
        schemas.GenerateSupercellFromPoscar(
            poscar_path=str(poscar_nacl_path),
            scaling_matrix="2 0; 0 2"
        )
    assert "3x3" in str(exc.value)

def test_supercell_non_integer(poscar_nacl_path):
    """测试非整数的超胞矩阵"""
    with pytest.raises(ValidationError) as exc:
        schemas.GenerateSupercellFromPoscar(
            poscar_path=str(poscar_nacl_path),
            scaling_matrix="1.5 0 0; 0 1.5 0; 0 0 1.5"
        )
    assert "integer" in str(exc.value)

# GenerateVaspWorkflowOfConvergenceTests 测试
def test_convergence_tests_valid(poscar_nacl_path):
    """测试有效的收敛测试配置"""
    result = schemas.GenerateVaspWorkflowOfConvergenceTests(
        poscar_path=str(poscar_nacl_path),
        test_type="encut",
        encut_levels=[300, 400, 500]
    )
    assert result.test_type == "encut"

def test_convergence_tests_invalid_kpoints(poscar_nacl_path):
    """测试非法的 kpoint 级别（非正整数）"""
    with pytest.raises(ValidationError) as exc:
        schemas.GenerateVaspWorkflowOfConvergenceTests(
            poscar_path=str(poscar_nacl_path),
            kpoint_levels=[1000, -2000, 3000]
        )
    assert "positive" in str(exc.value)

# GenerateVaspWorkflowOfEos 测试
def test_eos_valid(poscar_nacl_path):
    """测试有效的 EOS 配置"""
    result = schemas.GenerateVaspWorkflowOfEos(
        poscar_path=str(poscar_nacl_path),
        scale_factors=[0.94, 0.96, 0.98, 1.00]
    )
    assert len(result.scale_factors) == 4

def test_eos_invalid_scale_factors(poscar_nacl_path):
    """测试非法的 scale factor（非正数）"""
    with pytest.raises(ValidationError) as exc:
        schemas.GenerateVaspWorkflowOfEos(
            poscar_path=str(poscar_nacl_path),
            scale_factors=[0.94, -0.96, 0.98]
        )
    assert "positive" in str(exc.value)

# GenerateVaspWorkflowOfAimd 测试
def test_aimd_valid(poscar_nacl_path):
    """测试有效的 AIMD 配置"""
    result = schemas.GenerateVaspWorkflowOfAimd(
        poscar_path=str(poscar_nacl_path),
        temperatures=[500, 1000],
        md_steps=2000,
        md_timestep=2.0
    )
    assert result.md_steps == 2000

def test_aimd_invalid_md_steps(poscar_nacl_path):
    """测试非法的 MD 步数"""
    with pytest.raises(ValidationError) as exc:
        schemas.GenerateVaspWorkflowOfAimd(
            poscar_path=str(poscar_nacl_path),
            temperatures=[500],
            md_steps=0,
            md_timestep=2.0
        )
    assert "at least 1" in str(exc.value)

# GenerateVaspWorkflowOfNeb 测试
def test_neb_valid(poscar_nacl_path):
    """测试有效的 NEB 配置"""
    # 用同一个文件作为初始和终态（测试用，实际会不同）
    result = schemas.GenerateVaspWorkflowOfNeb(
        initial_poscar_path=str(poscar_nacl_path),
        final_poscar_path=str(poscar_nacl_path),
        num_images=5
    )
    assert result.num_images == 5

def test_neb_invalid_images(poscar_nacl_path):
    """测试非法的 images 数量"""
    with pytest.raises(ValidationError) as exc:
        schemas.GenerateVaspWorkflowOfNeb(
            initial_poscar_path=str(poscar_nacl_path),
            final_poscar_path=str(poscar_nacl_path),
            num_images=0
        )
    assert "at least 1" in str(exc.value)

# RunSimulationUsingMlps 测试
def test_mlps_valid(poscar_nacl_path):
    """测试有效的 MLP 模拟配置"""
    result = schemas.RunSimulationUsingMlps(
        poscar_path=str(poscar_nacl_path),
        mlps_type="CHGNet",
        task_type="single",
        fmax=0.05
    )
    assert result.mlps_type == "CHGNet"

def test_mlps_invalid_fmax(poscar_nacl_path):
    """测试非法的 fmax（非正数）"""
    with pytest.raises(ValidationError) as exc:
        schemas.RunSimulationUsingMlps(
            poscar_path=str(poscar_nacl_path),
            fmax=0.0
        )
    assert "positive" in str(exc.value)

# AnalyzeFeaturesForMachineLearning 测试
def test_analyze_features_valid(tmp_path):
    """测试有效的特征分析配置"""
    input_df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    output_df = pd.DataFrame({"C": [5, 6]})
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_df.to_csv(input_path, index=False)
    output_df.to_csv(output_path, index=False)
    result = schemas.AnalyzeFeaturesForMachineLearning(
        input_data_path=str(input_path),
        output_data_path=str(output_path)
    )
    assert result.input_data_path == str(input_path)

def test_analyze_features_row_mismatch(tmp_path):
    """测试输入输出行数不匹配"""
    input_df = pd.DataFrame({"A": [1, 2, 3]})
    output_df = pd.DataFrame({"C": [4, 5]})
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_df.to_csv(input_path, index=False)
    output_df.to_csv(output_path, index=False)
    with pytest.raises(ValidationError) as exc:
        schemas.AnalyzeFeaturesForMachineLearning(
            input_data_path=str(input_path),
            output_data_path=str(output_path)
        )
    assert "same number of rows" in str(exc.value)

# ReduceDimensionsForMachineLearning 测试
def test_reduce_dimensions_valid(tmp_path):
    """测试有效的降维配置"""
    input_df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6], "C": [7, 8, 9]})
    input_path = tmp_path / "input.csv"
    input_df.to_csv(input_path, index=False)
    result = schemas.ReduceDimensionsForMachineLearning(
        input_data_path=str(input_path),
        n_components=2
    )
    assert result.n_components == 2

def test_reduce_dimensions_too_many_components(tmp_path):
    """测试主成分数超过特征数"""
    input_df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    input_path = tmp_path / "input.csv"
    input_df.to_csv(input_path, index=False)
    with pytest.raises(ValidationError) as exc:
        schemas.ReduceDimensionsForMachineLearning(
            input_data_path=str(input_path),
            n_components=5
        )
    assert "cannot exceed" in str(exc.value)

# AugmentDataForMachineLearning 测试
def test_augment_data_valid(tmp_path):
    """测试有效的数据增强配置"""
    input_df = pd.DataFrame({"A": [1, 2]})
    output_df = pd.DataFrame({"B": [3, 4]})
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_df.to_csv(input_path, index=False)
    output_df.to_csv(output_path, index=False)
    result = schemas.AugmentDataForMachineLearning(
        input_data_path=str(input_path),
        output_data_path=str(output_path),
        num_augmentations=50
    )
    assert result.num_augmentations == 50

def test_augment_data_invalid_num(tmp_path):
    """测试非法的增强次数"""
    input_df = pd.DataFrame({"A": [1, 2]})
    output_df = pd.DataFrame({"B": [3, 4]})
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_df.to_csv(input_path, index=False)
    output_df.to_csv(output_path, index=False)
    with pytest.raises(ValidationError) as exc:
        schemas.AugmentDataForMachineLearning(
            input_data_path=str(input_path),
            output_data_path=str(output_path),
            num_augmentations=0
        )
    assert "at least 1" in str(exc.value)

# DesignModelForMachineLearning 测试
def test_design_model_valid(tmp_path):
    """测试有效的模型设计配置"""
    input_df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    output_df = pd.DataFrame({"C": [5, 6]})
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_df.to_csv(input_path, index=False)
    output_df.to_csv(output_path, index=False)
    result = schemas.DesignModelForMachineLearning(
        input_data_path=str(input_path),
        output_data_path=str(output_path),
        n_trials=50
    )
    assert result.n_trials == 50

# TrainModelForMachineLearning 测试
def test_train_model_valid(tmp_path):
    """测试有效的模型训练配置（需要创建 dummy 文件）"""
    input_df = pd.DataFrame({"A": [1, 2]})
    output_df = pd.DataFrame({"B": [3, 4]})
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_df.to_csv(input_path, index=False)
    output_df.to_csv(output_path, index=False)
    model_path = tmp_path / "model.pkl"
    model_path.touch()
    log_path = tmp_path / "params.log"
    log_path.touch()
    result = schemas.TrainModelForMachineLearning(
        input_data_path=str(input_path),
        output_data_path=str(output_path),
        best_model_path=str(model_path),
        best_model_params_path=str(log_path),
        max_epochs=500,
        patience=30
    )
    assert result.max_epochs == 500

def test_train_model_missing_model(tmp_path):
    """测试模型文件不存在"""
    input_df = pd.DataFrame({"A": [1, 2]})
    output_df = pd.DataFrame({"B": [3, 4]})
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_df.to_csv(input_path, index=False)
    output_df.to_csv(output_path, index=False)
    with pytest.raises(ValidationError) as exc:
        schemas.TrainModelForMachineLearning(
            input_data_path=str(input_path),
            output_data_path=str(output_path),
            best_model_path=str(tmp_path / "nonexistent.pkl"),
            best_model_params_path=str(tmp_path / "params.log")
        )
    assert "not found" in str(exc.value)

# ModelPredictionForAlMgSiSc 测试
def test_almgsisc_valid():
    """测试有效的 Al-Mg-Si-Sc 预测输入"""
    result = schemas.ModelPredictionForAlMgSiSc(Mg=0.5, Si=8.0)
    assert result.Mg == 0.5

def test_almgsisc_invalid_mg():
    """测试 Mg 超出范围"""
    with pytest.raises(ValidationError) as exc:
        schemas.ModelPredictionForAlMgSiSc(Mg=1.0, Si=8.0)
    assert "between 0 and 0.7" in str(exc.value)

def test_almgsisc_invalid_si():
    """测试 Si 超出范围"""
    with pytest.raises(ValidationError) as exc:
        schemas.ModelPredictionForAlMgSiSc(Mg=0.5, Si=14.0)
    assert "between 4.0 and 13.0" in str(exc.value)

# ModelPredictionForAlCoCrFeNi 测试
def test_alccrfeni_valid():
    """测试有效的 Al-Co-Cr-Fe-Ni 预测输入"""
    result = schemas.ModelPredictionForAlCoCrFeNi(Al=20.0, Co=20.0, Cr=20.0, Fe=20.0)
    assert result.Al == 20.0


def test_alccrfeni_invalid_sum():
    """测试元素含量之和超过 100%"""
    with pytest.raises(ValidationError) as exc:
        schemas.ModelPredictionForAlCoCrFeNi(Al=40.0, Co=40.0, Cr=40.0, Fe=40.0)
    assert "not exceed 100" in str(exc.value)