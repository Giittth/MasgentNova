# tests/test_ml_nn_design.py
"""测试 Optuna 超参数优化模块（完整修正版）"""

import pytest
import numpy as np
import pandas as pd
import torch
import optuna
from pathlib import Path
from unittest.mock import patch, MagicMock

import masgent.ml.ml_nn_design as ml_nn_design


# ---------- Fixtures ----------
@pytest.fixture
def sample_data(tmp_path):
    """生成训练数据 CSV 文件并返回路径（Path 对象）"""
    np.random.seed(42)
    X = np.random.rand(50, 4)
    Y = np.random.rand(50, 2)
    X_df = pd.DataFrame(X, columns=["F1", "F2", "F3", "F4"])
    Y_df = pd.DataFrame(Y, columns=["T1", "T2"])

    x_path = tmp_path / "input.csv"
    y_path = tmp_path / "output.csv"
    X_df.to_csv(x_path, index=False)
    Y_df.to_csv(y_path, index=False)
    return x_path, y_path, tmp_path


@pytest.fixture
def mock_trial():
    """模拟 optuna.trial 对象，支持 log 参数"""
    trial = MagicMock()
    trial.suggest_int.side_effect = lambda name, low, high, step=1: low if name == "n_layers" else 16
    trial.suggest_float.side_effect = lambda name, low, high, log=False: low + (high - low) * 0.5
    trial.suggest_categorical.side_effect = lambda name, choices: choices[0]
    trial.should_prune.return_value = False
    trial.number = 0
    return trial


# ---------- 测试 define_model ----------
@patch('masgent.ml.ml_nn_design.pd.read_csv')
def test_define_model(mock_read_csv, mock_trial):
    """测试模型定义返回正确的 Sequential 结构"""
    def read_side_effect(path):
        if 'input' in str(path):
            return MagicMock(shape=(50, 4))
        else:
            return MagicMock(shape=(50, 2))
    mock_read_csv.side_effect = read_side_effect

    ml_nn_design.INPUT_DATA = "dummy_input.csv"
    ml_nn_design.OUTPUT_DATA = "dummy_output.csv"
    ml_nn_design.LAYERS_MIN, ml_nn_design.LAYERS_MAX, ml_nn_design.LAYERS_STEP = 1, 2, 1
    ml_nn_design.NODES_MIN, ml_nn_design.NODES_MAX, ml_nn_design.NODES_STEP = 8, 32, 2
    ml_nn_design.DROPOUT_MIN, ml_nn_design.DROPOUT_MAX = 0.0, 0.5

    model = ml_nn_design.define_model(mock_trial)
    assert isinstance(model, torch.nn.Sequential)
    assert model[0].in_features == 4
    assert model[-1].out_features == 2


# ---------- 测试 objective ----------
@patch('masgent.ml.ml_nn_design.get_scaler')
@patch('masgent.ml.ml_nn_design.KFold')
@patch('masgent.ml.ml_nn_design.tqdm')
@patch('masgent.ml.ml_nn_design.pd.read_csv')
def test_objective(mock_read_csv, mock_tqdm, mock_kfold, mock_get_scaler, sample_data, mock_trial):
    """测试目标函数执行一次迭代并返回准确率"""
    X_path, Y_path, tmp_path = sample_data

    # ===== 设置所有必需的全局变量 =====
    ml_nn_design.INPUT_DATA = str(X_path)
    ml_nn_design.OUTPUT_DATA = str(Y_path)
    ml_nn_design.SAVE_PATH = str(tmp_path)
    ml_nn_design.DEVICE = torch.device('cpu')
    ml_nn_design.LAYERS_MIN, ml_nn_design.LAYERS_MAX, ml_nn_design.LAYERS_STEP = 1, 2, 1
    ml_nn_design.NODES_MIN, ml_nn_design.NODES_MAX, ml_nn_design.NODES_STEP = 8, 16, 2
    ml_nn_design.DROPOUT_MIN, ml_nn_design.DROPOUT_MAX = 0.0, 0.5
    ml_nn_design.OPTIMIZERS = ['Adam', 'SGD', 'RMSprop']
    ml_nn_design.LR_MIN, ml_nn_design.LR_MAX = 1e-4, 1e-2
    ml_nn_design.WD_MIN, ml_nn_design.WD_MAX = 1e-6, 1e-4
    # 初始化全局变量（在 objective 中会使用）
    ml_nn_design.CURRENT_ACCURACY = 1e10
    ml_nn_design.FOUND_NEW = False

    # ===== 创建 objective 中会用到的子目录 =====
    (tmp_path / "tested_models").mkdir(exist_ok=True)
    (tmp_path / "best_model_losses").mkdir(exist_ok=True)

    # ===== Mock pd.read_csv =====
    def read_csv_side_effect(filepath):
        if 'input' in str(filepath):
            return pd.DataFrame(np.random.rand(50, 4), columns=[f"F{i}" for i in range(4)])
        else:
            return pd.DataFrame(np.random.rand(50, 2), columns=["T1", "T2"])
    mock_read_csv.side_effect = read_csv_side_effect

    # ===== Mock get_scaler =====
    def scaler_side_effect(data_scaler):
        if 'input' in str(data_scaler):
            scaler = MagicMock()
            scaler.transform.return_value = np.random.rand(50, 4)
            return scaler
        else:
            scaler = MagicMock()
            scaler.transform.return_value = np.random.rand(50, 2)
            return scaler
    mock_get_scaler.side_effect = scaler_side_effect

    # ===== Mock KFold =====
    mock_split = MagicMock()
    mock_split.return_value = [(range(40), range(10))]
    mock_kfold.return_value.split.return_value = mock_split.return_value

    # ===== Mock tqdm =====
    mock_tqdm.return_value = range(1)  # 只运行 1 个 epoch

    # 执行 objective
    accuracy = ml_nn_design.objective(mock_trial)

    assert isinstance(accuracy, float)
    # 验证模型文件被创建
    model_file = tmp_path / "tested_models" / "model_0.pkl"
    assert model_file.exists()


# ---------- 测试 optimize ----------
@patch('masgent.ml.ml_nn_design.draw_study')  # mock draw_study 避免参数重要性计算失败
@patch('masgent.ml.ml_nn_design.get_scaler')
@patch('masgent.ml.ml_nn_design.KFold')
@patch('masgent.ml.ml_nn_design.tqdm')
@patch('masgent.ml.ml_nn_design.pd.read_csv')
def test_optimize_basic(mock_read_csv, mock_tqdm, mock_kfold, mock_get_scaler, mock_draw_study, sample_data):
    """测试优化主流程（运行一次 trial 并验证文件生成）"""
    X_path, Y_path, tmp_path = sample_data
    save_path = tmp_path / "optuna_results"

    # ===== 设置所有必需的全局变量 =====
    ml_nn_design.INPUT_DATA = str(X_path)
    ml_nn_design.OUTPUT_DATA = str(Y_path)
    ml_nn_design.SAVE_PATH = str(save_path)
    ml_nn_design.DEVICE = torch.device('cpu')
    ml_nn_design.LAYERS_MIN, ml_nn_design.LAYERS_MAX, ml_nn_design.LAYERS_STEP = 1, 2, 1
    ml_nn_design.NODES_MIN, ml_nn_design.NODES_MAX, ml_nn_design.NODES_STEP = 8, 16, 2
    ml_nn_design.DROPOUT_MIN, ml_nn_design.DROPOUT_MAX = 0.0, 0.5
    ml_nn_design.OPTIMIZERS = ['Adam', 'SGD', 'RMSprop']
    ml_nn_design.LR_MIN, ml_nn_design.LR_MAX = 1e-4, 1e-2
    ml_nn_design.WD_MIN, ml_nn_design.WD_MAX = 1e-6, 1e-4
    # 初始化全局变量
    ml_nn_design.CURRENT_ACCURACY = 1e10
    ml_nn_design.FOUND_NEW = False

    # ===== Mock pd.read_csv =====
    def read_csv_side_effect(filepath):
        if 'input' in str(filepath):
            return pd.DataFrame(np.random.rand(50, 4), columns=[f"F{i}" for i in range(4)])
        else:
            return pd.DataFrame(np.random.rand(50, 2), columns=["T1", "T2"])
    mock_read_csv.side_effect = read_csv_side_effect

    # ===== Mock get_scaler =====
    def scaler_side_effect(data_scaler):
        if 'input' in str(data_scaler):
            scaler = MagicMock()
            scaler.transform.return_value = np.random.rand(50, 4)
            return scaler
        else:
            scaler = MagicMock()
            scaler.transform.return_value = np.random.rand(50, 2)
            return scaler
    mock_get_scaler.side_effect = scaler_side_effect

    # ===== Mock KFold =====
    mock_split = MagicMock()
    mock_split.return_value = [(range(40), range(10))]
    mock_kfold.return_value.split.return_value = mock_split.return_value

    # ===== Mock tqdm =====
    mock_tqdm.return_value = range(1)

    # 调用 optimize（实际运行 1 个 trial）
    ml_nn_design.optimize(
        input_data=str(X_path),
        output_data=str(Y_path),
        n_trials=1,
        save_path=str(save_path)
    )

    # 验证输出文件
    assert (save_path / "best_model.pkl").exists()
    assert (save_path / "study.pkl").exists()
    assert (save_path / "best_model_params.log").exists()
    # draw_study 被 mock，所以不检查绘图文件


# ---------- 测试 draw_study ----------
def test_draw_study(sample_data, tmp_path):
    """测试绘图函数生成图像文件"""
    X_path, Y_path, _ = sample_data
    study = optuna.create_study(direction='minimize')
    for i in range(5):
        study.add_trial(optuna.trial.create_trial(
            params={
                "lr": 0.001,
                "n_layers": 2,
                "optimizer": "Adam",
                "weight_decay": 0.0001
            },
            value=np.random.rand() * 0.1,
            distributions={
                "lr": optuna.distributions.FloatDistribution(1e-4, 1e-2, log=True),
                "n_layers": optuna.distributions.IntDistribution(1, 4),
                "optimizer": optuna.distributions.CategoricalDistribution(["Adam", "SGD"]),
                "weight_decay": optuna.distributions.FloatDistribution(1e-6, 1e-4, log=True),
            }
        ))

    study_path = tmp_path / "study.pkl"
    import joblib
    joblib.dump(study, study_path)

    ml_nn_design.draw_study(str(study_path))

    assert (tmp_path / "study.csv").exists()
    assert (tmp_path / "study_history.png").exists()
    assert (tmp_path / "study_importance.png").exists()
    assert (tmp_path / "study_slice.png").exists()


# ---------- 异常测试 ----------
def test_optimize_missing_input(sample_data):
    """测试输入文件不存在时抛出异常"""
    X_path, _, tmp_path = sample_data
    with pytest.raises(FileNotFoundError):
        ml_nn_design.optimize(
            input_data="/nonexistent.csv",
            output_data=str(X_path),
            n_trials=2,
            save_path=str(tmp_path)
        )


def test_optimize_invalid_n_trials(sample_data):
    """测试 n_trials 为 0 时抛出 ValueError"""
    X_path, Y_path, tmp_path = sample_data
    ml_nn_design.INPUT_DATA = str(X_path)
    ml_nn_design.OUTPUT_DATA = str(Y_path)
    ml_nn_design.SAVE_PATH = str(tmp_path / "zero")
    ml_nn_design.DEVICE = torch.device('cpu')
    ml_nn_design.LAYERS_MIN, ml_nn_design.LAYERS_MAX, ml_nn_design.LAYERS_STEP = 1, 2, 1
    ml_nn_design.NODES_MIN, ml_nn_design.NODES_MAX, ml_nn_design.NODES_STEP = 8, 16, 2
    ml_nn_design.DROPOUT_MIN, ml_nn_design.DROPOUT_MAX = 0.0, 0.5
    ml_nn_design.OPTIMIZERS = ['Adam', 'SGD', 'RMSprop']
    ml_nn_design.LR_MIN, ml_nn_design.LR_MAX = 1e-4, 1e-2
    ml_nn_design.WD_MIN, ml_nn_design.WD_MAX = 1e-6, 1e-4

    with pytest.raises(ValueError, match="No trials are completed yet"):
        ml_nn_design.optimize(
            input_data=str(X_path),
            output_data=str(Y_path),
            n_trials=0,
            save_path=str(tmp_path / "zero")
        )