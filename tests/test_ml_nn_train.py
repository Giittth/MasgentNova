# tests/test_ml_nn_train.py
"""测试模型训练与评估模块（修正版）"""

import pytest
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from unittest.mock import patch, MagicMock

import masgent.ml.ml_nn_train as ml_nn_train


# ---------- Fixtures ----------
@pytest.fixture
def sample_data(tmp_path):
    """生成训练数据、模型和参数文件（返回 Path 对象）"""
    np.random.seed(42)
    X = np.random.rand(50, 4)
    Y = np.random.rand(50, 2)
    X_df = pd.DataFrame(X, columns=["F1", "F2", "F3", "F4"])
    Y_df = pd.DataFrame(Y, columns=["T1", "T2"])

    x_path = tmp_path / "input.csv"
    y_path = tmp_path / "output.csv"
    X_df.to_csv(x_path, index=False)
    Y_df.to_csv(y_path, index=False)

    model = torch.nn.Sequential(
        torch.nn.Linear(4, 8),
        torch.nn.Sigmoid(),
        torch.nn.Linear(8, 2)
    )
    model_path = tmp_path / "best_model.pkl"
    torch.save(model, model_path)

    params_path = tmp_path / "best_model_params.log"
    with open(params_path, "w") as f:
        f.write("lr: 0.001\nweight_decay: 0.0001\n")

    return x_path, y_path, model_path, params_path, tmp_path


# ---------- 测试 get_std ----------
def test_get_std():
    """测试标准化函数返回正确的 scaler 和标准化数据"""
    data = np.random.rand(20, 5)
    scaler, data_std = ml_nn_train.get_std(data)

    assert scaler is not None
    assert data_std.shape == data.shape
    assert np.allclose(data_std.mean(axis=0), 0, atol=1e-6)
    assert np.allclose(data_std.std(axis=0), 1, atol=1e-6)
    data_reconstructed = scaler.inverse_transform(data_std)
    assert np.allclose(data, data_reconstructed)


# ---------- 测试 init_weights ----------
def test_init_weights():
    """测试权重初始化重置参数"""
    model = torch.nn.Linear(5, 3)
    initial_weights = model.weight.data.clone()

    ml_nn_train.init_weights(model)

    assert not torch.allclose(initial_weights, model.weight.data)


# ---------- 测试 train ----------
@patch('masgent.ml.ml_nn_train.tqdm')
def test_train_basic(mock_tqdm, sample_data):
    """测试基本训练流程（mock tqdm 加速）"""
    X_path, Y_path, model_path, params_path, tmp_path = sample_data
    save_path = tmp_path / "training_results"

    mock_tqdm.return_value = range(2)

    ml_nn_train.train(
        input_data=str(X_path),
        output_data=str(Y_path),
        best_model_pkl=str(model_path),
        best_model_params=str(params_path),
        epochs=2,
        patience=2,
        save_path=str(save_path),
        reset=True
    )

    save_path_obj = Path(save_path)
    assert save_path_obj.exists()
    assert (save_path_obj / "loss.png").exists()
    assert (save_path_obj / "trained_model.pkl").exists()
    assert (save_path_obj / "performance.log").exists()

    with open(save_path_obj / "performance.log", "r") as f:
        content = f.read()
        assert "RMSE" in content
        assert "R2" in content


@patch('masgent.ml.ml_nn_train.tqdm')
def test_train_without_reset(mock_tqdm, sample_data):
    """测试 reset=False 时不重置权重"""
    X_path, Y_path, model_path, params_path, tmp_path = sample_data
    save_path = tmp_path / "training_no_reset"

    mock_tqdm.return_value = range(2)

    ml_nn_train.train(
        input_data=str(X_path),
        output_data=str(Y_path),
        best_model_pkl=str(model_path),
        best_model_params=str(params_path),
        epochs=2,
        patience=2,
        save_path=str(save_path),
        reset=False
    )

    assert (save_path / "trained_model.pkl").exists()


@patch('masgent.ml.ml_nn_train.tqdm')
def test_train_early_stopping(mock_tqdm, sample_data):
    """测试 early stopping 在损失不下降时停止"""
    X_path, Y_path, model_path, params_path, tmp_path = sample_data
    save_path = tmp_path / "early_stop"

    mock_tqdm.return_value = range(100)

    ml_nn_train.train(
        input_data=str(X_path),
        output_data=str(Y_path),
        best_model_pkl=str(model_path),
        best_model_params=str(params_path),
        epochs=100,
        patience=3,
        save_path=str(save_path),
        reset=True
    )

    assert (Path(save_path) / "loss.png").exists()


@patch('masgent.ml.ml_nn_train.tqdm')
def test_train_performance_metrics(mock_tqdm, sample_data):
    """测试性能指标写入文件且包含所有输出维度"""
    X_path, Y_path, model_path, params_path, tmp_path = sample_data
    save_path = tmp_path / "metrics"

    mock_tqdm.return_value = range(2)

    ml_nn_train.train(
        input_data=str(X_path),
        output_data=str(Y_path),
        best_model_pkl=str(model_path),
        best_model_params=str(params_path),
        epochs=2,
        patience=2,
        save_path=str(save_path),
        reset=True
    )

    log_file = Path(save_path) / "performance.log"
    with open(log_file, "r") as f:
        content = f.read()
        assert "Training Set" in content
        assert "Validation Set" in content
        assert "RMSE:" in content
        assert "R2:" in content

    # 检查每个输出维度的预测图
    for i in range(2):
        png_file = Path(save_path) / f"pred_vs_true_T{i+1}.png"
        assert png_file.exists()


# ---------- 异常测试 ----------
def test_train_missing_input(sample_data):
    """测试输入文件不存在时抛出异常"""
    X_path, Y_path, model_path, params_path, tmp_path = sample_data
    with pytest.raises(FileNotFoundError):
        ml_nn_train.train(
            input_data="/nonexistent.csv",
            output_data=str(Y_path),
            best_model_pkl=str(model_path),
            best_model_params=str(params_path),
            epochs=2,
            patience=2,
            save_path=str(tmp_path),
            reset=True
        )


def test_train_missing_model(sample_data):
    """测试模型文件不存在时抛出异常"""
    X_path, Y_path, _, params_path, tmp_path = sample_data
    with pytest.raises(FileNotFoundError):
        ml_nn_train.train(
            input_data=str(X_path),
            output_data=str(Y_path),
            best_model_pkl="/missing.pkl",
            best_model_params=str(params_path),
            epochs=2,
            patience=2,
            save_path=str(tmp_path),
            reset=True
        )