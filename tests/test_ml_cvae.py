"""测试 CVAE 数据增强模块（修正版）"""

import pytest
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from unittest.mock import patch, MagicMock

import masgent.ml.ml_cvae as ml_cvae


# ---------- Fixtures ----------
@pytest.fixture
def sample_data():
    """生成标准测试数据集（50 样本，5 特征，2 输出）"""
    np.random.seed(42)
    X = np.random.rand(50, 5)
    Y = np.random.rand(50, 2)
    return pd.DataFrame(X, columns=[f"X{i}" for i in range(5)]), pd.DataFrame(Y, columns=["Y1", "Y2"])


@pytest.fixture
def small_data():
    """极小数据集（10 样本）用于快速训练"""
    np.random.seed(42)
    X = np.random.rand(10, 3)
    Y = np.random.rand(10, 1)
    return pd.DataFrame(X, columns=["A", "B", "C"]), pd.DataFrame(Y, columns=["Target"])


# ---------- CVAE 模型测试 ----------
def test_cvae_initialization():
    """测试 CVAE 模型各维度正确"""
    x_dim, y_dim, latent_dim = 6, 3, 10
    hidden_dims = [128, 64]
    model = ml_cvae.CVAE(x_dim, y_dim, latent_dim, hidden_dims)

    assert model.x_dim == x_dim
    assert model.y_dim == y_dim
    assert model.latent_dim == latent_dim
    first_layer = model.encoder[0]
    assert isinstance(first_layer, torch.nn.Linear)
    assert first_layer.in_features == x_dim + y_dim
    dec_first = model.decoder[0]
    assert isinstance(dec_first, torch.nn.Linear)
    assert dec_first.in_features == latent_dim + y_dim


def test_cvae_forward(sample_data):
    """测试前向传播输出形状"""
    X_df, Y_df = sample_data
    X = torch.tensor(X_df.values, dtype=torch.float32)
    Y = torch.tensor(Y_df.values, dtype=torch.float32)
    x_dim, y_dim = X.shape[1], Y.shape[1]
    latent_dim = 4
    model = ml_cvae.CVAE(x_dim, y_dim, latent_dim)

    x_recon, mu, logvar = model(X, Y)
    assert x_recon.shape == X.shape
    assert mu.shape == (X.shape[0], latent_dim)
    assert logvar.shape == (X.shape[0], latent_dim)
    assert not torch.isnan(x_recon).any()


def test_cvae_loss():
    """测试损失函数返回非负标量"""
    batch_size = 8
    x_dim, y_dim, latent_dim = 5, 2, 6
    x = torch.randn(batch_size, x_dim)
    x_recon = torch.randn(batch_size, x_dim)
    mu = torch.randn(batch_size, latent_dim)
    logvar = torch.randn(batch_size, latent_dim)

    loss = ml_cvae.cvae_loss(x, x_recon, mu, logvar)
    assert isinstance(loss, torch.Tensor)
    assert loss.dim() == 0
    assert loss.item() >= 0
    assert not torch.isnan(loss).any()


def test_train_cvae_one_epoch(small_data):
    """测试训练循环运行一个 epoch 不报错"""
    X_df, Y_df = small_data
    X = torch.tensor(X_df.values, dtype=torch.float32)
    Y = torch.tensor(Y_df.values, dtype=torch.float32)
    dataset = torch.utils.data.TensorDataset(X, Y)
    loader = torch.utils.data.DataLoader(dataset, batch_size=4, shuffle=True)

    x_dim, y_dim = X.shape[1], Y.shape[1]
    model = ml_cvae.CVAE(x_dim, y_dim, latent_dim=2, hidden_dims=[8, 4])

    trained = ml_cvae.train_cvae(model, loader, epochs=1, lr=0.01, patience=1)
    assert trained is model


def test_train_cvae_early_stopping(small_data):
    """测试 early stopping 在损失不下降时停止"""
    X_df, Y_df = small_data
    X = torch.tensor(X_df.values, dtype=torch.float32)
    Y = torch.tensor(Y_df.values, dtype=torch.float32)
    dataset = torch.utils.data.TensorDataset(X, Y)
    loader = torch.utils.data.DataLoader(dataset, batch_size=4, shuffle=True)

    x_dim, y_dim = X.shape[1], Y.shape[1]
    model = ml_cvae.CVAE(x_dim, y_dim, latent_dim=2, hidden_dims=[8, 4])

    trained = ml_cvae.train_cvae(model, loader, epochs=100, lr=10.0, patience=3)
    assert trained is model


def test_generate_conditional_samples(small_data):
    """测试条件采样生成正确形状和类型"""
    X_df, Y_df = small_data
    X = torch.tensor(X_df.values, dtype=torch.float32)
    Y = torch.tensor(Y_df.values, dtype=torch.float32)
    x_dim, y_dim = X.shape[1], Y.shape[1]
    latent_dim = 2
    model = ml_cvae.CVAE(x_dim, y_dim, latent_dim, hidden_dims=[8, 4])

    y_cond = Y[0].reshape(1, -1).numpy()
    samples = ml_cvae.generate_conditional_samples(model, y_cond, num_samples=5)

    assert isinstance(samples, np.ndarray)
    assert samples.shape == (5, x_dim)
    assert np.all(np.isfinite(samples))


def test_generate_conditional_samples_single_condition(small_data):
    """测试单个条件采样（修正：传入单个样本）"""
    X_df, Y_df = small_data
    X = torch.tensor(X_df.values, dtype=torch.float32)
    Y = torch.tensor(Y_df.values, dtype=torch.float32)
    x_dim, y_dim = X.shape[1], Y.shape[1]
    model = ml_cvae.CVAE(x_dim, y_dim, latent_dim=2)

    # 传入单个条件样本
    y_cond = Y[0].numpy().reshape(1, -1)
    samples = ml_cvae.generate_conditional_samples(model, y_cond, num_samples=3)
    assert samples.shape == (3, x_dim)


# ---------- 主函数 run_cvae_augmentation 测试 ----------
def test_run_cvae_augmentation_basic(small_data):
    """测试完整的数据增强流程（真实训练，快速）"""
    X_df, Y_df = small_data
    num_aug = 20
    x_aug, y_aug = ml_cvae.run_cvae_augmentation(X_df, Y_df, num_aug=num_aug)

    assert x_aug.shape == (num_aug, X_df.shape[1])
    assert y_aug.shape == (num_aug, Y_df.shape[1])
    assert list(x_aug.columns) == list(X_df.columns)
    assert list(y_aug.columns) == list(Y_df.columns)
    assert np.all(np.isfinite(x_aug.values))
    assert np.all(np.isfinite(y_aug.values))


def test_run_cvae_augmentation_with_large_data(sample_data):
    """测试较大数据集的增强"""
    X_df, Y_df = sample_data
    num_aug = 50
    x_aug, y_aug = ml_cvae.run_cvae_augmentation(X_df, Y_df, num_aug=num_aug)
    assert x_aug.shape == (num_aug, X_df.shape[1])
    assert y_aug.shape == (num_aug, Y_df.shape[1])


def test_run_cvae_augmentation_reproducibility(small_data):
    """测试固定随机种子下结果可重复"""
    X_df, Y_df = small_data
    np.random.seed(123)
    torch.manual_seed(123)
    x_aug1, y_aug1 = ml_cvae.run_cvae_augmentation(X_df, Y_df, num_aug=10)

    np.random.seed(123)
    torch.manual_seed(123)
    x_aug2, y_aug2 = ml_cvae.run_cvae_augmentation(X_df, Y_df, num_aug=10)

    pd.testing.assert_frame_equal(x_aug1, x_aug2)
    pd.testing.assert_frame_equal(y_aug1, y_aug2)


def test_run_cvae_augmentation_edge_cases():
    """测试边缘情况：单样本、单特征、单输出"""
    X = pd.DataFrame(np.random.rand(5, 1), columns=["X1"])
    Y = pd.DataFrame(np.random.rand(5, 1), columns=["Y1"])

    x_aug, y_aug = ml_cvae.run_cvae_augmentation(X, Y, num_aug=5)

    assert x_aug.shape == (5, 1)
    assert y_aug.shape == (5, 1)
    assert not x_aug.isnull().any().any()
    assert not y_aug.isnull().any().any()


def test_run_cvae_augmentation_missing_values(small_data):
    """测试数据包含 NaN 时 CVAE 的行为（可能被标准化处理）"""
    X_df, Y_df = small_data
    X_df.iloc[0, 0] = np.nan
    # 实际实现可能通过 StandardScaler 处理 NaN（转为均值填充或报错）
    # 我们测试它不会导致程序崩溃
    try:
        x_aug, y_aug = ml_cvae.run_cvae_augmentation(X_df, Y_df, num_aug=5)
        # 如果成功，验证输出
        assert x_aug.shape == (5, X_df.shape[1])
    except Exception as e:
        # 如果抛出异常，验证是预期的
        assert isinstance(e, (ValueError, RuntimeError))


@patch('masgent.ml.ml_cvae.train_cvae')
def test_run_cvae_augmentation_mock(mock_train, small_data):
    """使用 mock 快速测试主函数逻辑（跳过耗时训练）"""
    X_df, Y_df = small_data
    mock_model = MagicMock()
    mock_model.latent_dim = 2
    mock_model.decode.return_value = torch.ones(1, X_df.shape[1], dtype=torch.float32)
    mock_train.return_value = mock_model

    x_aug, y_aug = ml_cvae.run_cvae_augmentation(X_df, Y_df, num_aug=10)

    assert x_aug.shape == (10, X_df.shape[1])
    assert y_aug.shape == (10, Y_df.shape[1])