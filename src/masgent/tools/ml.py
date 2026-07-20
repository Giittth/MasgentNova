# src/masgent/tools/ml.py
"""机器学习：特征分析、降维、数据增强、模型设计、训练、重训练、预训练预测"""

import os, pickle
import numpy as np
import pandas as pd
import joblib
import torch
from pathlib import Path
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from masgent.models import schemas
from masgent.utils import list_files_in_dir
from masgent._config import config
from masgent.ml import run_cvae_augmentation, optimize, train
from .core import with_metadata


@with_metadata(schemas.ToolMetadata(
    name='Analyze features for machine learning',
    description='Analyze features (correlation matrix) for machine learning based on given input and output datasets',
    requires=['input_data_path', 'output_data_path'],
    optional=[],
    defaults={},
    prereqs=[],
))
def analyze_features_for_machine_learning(
    input_data_path: str,
    output_data_path: str,
) -> dict:
    '''
    Analyze features (correlation matrix) for machine learning based on given input and output datasets
    '''
    try:
        schemas.AnalyzeFeaturesForMachineLearning(
            input_data_path=input_data_path,
            output_data_path=output_data_path,
        )
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = str(config.get_runs_dir())

        machine_learning_dir = os.path.join(runs_dir, 'machine_learning')
        os.makedirs(machine_learning_dir, exist_ok=True)

        ml_feature_analysis_dir = os.path.join(machine_learning_dir, 'ml_feature_analysis')
        os.makedirs(ml_feature_analysis_dir, exist_ok=True)

        input_df = pd.read_csv(input_data_path)
        output_df = pd.read_csv(output_data_path)
        # Save the input and output data in machine learning directory for reference
        input_df.to_csv(os.path.join(machine_learning_dir, 'ml_input_data.csv'), index=False, float_format='%.8f')
        output_df.to_csv(os.path.join(machine_learning_dir, 'ml_output_data.csv'), index=False, float_format='%.8f')

        combined_df = pd.concat([input_df, output_df], axis=1)
        corr_matrix = combined_df.corr()
        corr_matrix.to_csv(os.path.join(ml_feature_analysis_dir, 'correlation_matrix.csv'), float_format='%.8f')
        
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend for plotting
        import matplotlib.pyplot as plt
        import seaborn as sns

        sns.set_theme(font_scale=1.0, style='whitegrid')
        matplotlib.rcParams['xtick.direction'] = 'in'
        matplotlib.rcParams['ytick.direction'] = 'in'
        fig = plt.figure(figsize=(13, 12), constrained_layout=True)
        ax = plt.subplot()
        sns.heatmap(
            corr_matrix, 
            annot=True, 
            fmt='.2f',
            cmap='coolwarm', 
            center=0, 
            cbar=False, 
            ax=ax
            )
        ax.set_title('Masgent Feature Correlation Matrix')
        plt.savefig(os.path.join(ml_feature_analysis_dir, 'correlation_matrix.png'), dpi=330)
        plt.close()

        return {
            'status': 'success',
            'message': f'Completed feature analysis for machine learning in {ml_feature_analysis_dir}.',
            'ml_feature_analysis_dir': ml_feature_analysis_dir,
            'correlation_matrix_csv_path': os.path.join(ml_feature_analysis_dir, 'correlation_matrix.csv'),
            'correlation_matrix_png_path': os.path.join(ml_feature_analysis_dir, 'correlation_matrix.png'),
            'input_data_path': os.path.join(machine_learning_dir, 'ml_input_data.csv'),
            'output_data_path': os.path.join(machine_learning_dir, 'ml_output_data.csv'),
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Feature analysis for machine learning failed: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Reduce dimensions for machine learning',
    description='Reduce dimensions for machine learning based on given input dataset using PCA method',
    requires=['input_data_path'],
    optional=['n_components'],
    defaults={'n_components': 2},
    prereqs=[],
))
def reduce_dimensions_for_machine_learning(
    input_data_path: str,
    n_components: int = 2,
) -> dict:
    '''
    Reduce dimensions for machine learning based on given input dataset using PCA method
    '''
    try:
        schemas.ReduceDimensionsForMachineLearning(
            input_data_path=input_data_path,
            n_components=n_components,
        )
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = str(config.get_runs_dir())

        machine_learning_dir = os.path.join(runs_dir, 'machine_learning')
        os.makedirs(machine_learning_dir, exist_ok=True)

        ml_dimension_reduction_dir = os.path.join(machine_learning_dir, 'ml_dimension_reduction')
        os.makedirs(ml_dimension_reduction_dir, exist_ok=True)

        input_df = pd.read_csv(input_data_path)

        from sklearn.decomposition import PCA
        reducer = PCA(n_components=n_components)
        joblib.dump(reducer, os.path.join(ml_dimension_reduction_dir, "pca_reducer.pkl"))
        reduced_data = reducer.fit_transform(input_df.values)
        reduced_df = pd.DataFrame(reduced_data, columns=[f'Component_{i+1}' for i in range(n_components)])
        reduced_df.to_csv(os.path.join(ml_dimension_reduction_dir, 'ml_input_data_reduced.csv'), index=False, float_format='%.8f')

        return {
            'status': 'success',
            'message': f'Completed dimension reduction for machine learning in {ml_dimension_reduction_dir}.',
            'input_data_reduced_path': os.path.join(ml_dimension_reduction_dir, 'ml_input_data_reduced.csv'),
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Dimension reduction for machine learning failed: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Augment data for machine learning',
    description='Augment data for machine learning based on given input and output datasets using VAE-based method',
    requires=['input_data_path', 'output_data_path'],
    optional=['num_augmentations', 'max_epochs', 'loss_threshold'],
    defaults={'num_augmentations': 100},
    prereqs=[],
))
def augment_data_for_machine_learning(
    input_data_path: str,
    output_data_path: str,
    num_augmentations: int = 100,
) -> dict:
    '''
    Augment data for machine learning by VAE-based method
    '''
    try:
        schemas.AugmentDataForMachineLearning(
            input_data_path=input_data_path,
            output_data_path=output_data_path,
            num_augmentations=num_augmentations,
        )
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = str(config.get_runs_dir())

        machine_learning_dir = os.path.join(runs_dir, 'machine_learning')
        os.makedirs(machine_learning_dir, exist_ok=True)

        ml_data_augmentation_dir = os.path.join(machine_learning_dir, 'ml_data_augmentation')
        os.makedirs(ml_data_augmentation_dir, exist_ok=True)

        input_df = pd.read_csv(input_data_path)
        output_df = pd.read_csv(output_data_path)

        # Run VAE for data augmentation
        from masgent.utils.ml_cvae import run_cvae_augmentation

        x_aug_df, y_aug_df = run_cvae_augmentation(input_df=input_df, output_df=output_df, num_aug=num_augmentations)
        x_all_df = pd.concat([input_df, x_aug_df], ignore_index=True)
        y_all_df = pd.concat([output_df, y_aug_df], ignore_index=True)
        x_all_df.to_csv(os.path.join(ml_data_augmentation_dir, 'ml_input_data_augmented.csv'), index=False, float_format='%.8f')
        y_all_df.to_csv(os.path.join(ml_data_augmentation_dir, 'ml_output_data_augmented.csv'), index=False, float_format='%.8f')

        return {
            'status': 'success',
            'message': f'Completed data augmentation for machine learning in {ml_data_augmentation_dir}.',
            'input_data_augmented_path': os.path.join(ml_data_augmentation_dir, 'ml_input_data_augmented.csv'),
            'output_data_augmented_path': os.path.join(ml_data_augmentation_dir, 'ml_output_data_augmented.csv'),
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Data augmentation for machine learning failed: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Design model for machine learning',
    description='Design model for machine learning using Optuna-based hyperparameter optimization based on given input and output datasets',
    requires=['input_data_path', 'output_data_path'],
    optional=['n_trials'],
    defaults={'n_trials': 100},
    prereqs=[],
))
def design_model_for_machine_learning(
    input_data_path: str,
    output_data_path: str,
    n_trials: int = 100,
) -> dict:
    '''
    Design model for machine learning using Optuna-based hyperparameter optimization
    '''
    try:
        schemas.DesignModelForMachineLearning(
            input_data_path=input_data_path,
            output_data_path=output_data_path,
            n_trials=n_trials,
        )
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = str(config.get_runs_dir())

        machine_learning_dir = os.path.join(runs_dir, 'machine_learning')
        os.makedirs(machine_learning_dir, exist_ok=True)

        ml_model_design_dir = os.path.join(machine_learning_dir, 'ml_model_design')
        os.makedirs(ml_model_design_dir, exist_ok=True)

        # Run Optuna for model design
        from masgent.utils.ml_nn_design import optimize

        optimize(
            input_data=input_data_path,
            output_data=output_data_path,
            save_path=ml_model_design_dir,
            n_trials=n_trials,
        )

        ml_files = list_files_in_dir(ml_model_design_dir)

        return {
            'status': 'success',
            'message': f'Completed model design for machine learning in {ml_model_design_dir}.',
            'ml_model_design_files': ml_files,
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Model design for machine learning failed: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Train & evaluate model for machine learning',
    description='Train model for machine learning based on given input and output datasets as well as best model structure and parameters',
    requires=['input_data_path', 'output_data_path', 'best_model_path', 'best_model_params_path'],
    optional=['max_epochs', 'patience'],
    defaults={'max_epochs': 1000, 'patience': 50},
    prereqs=[],
))
def train_model_for_machine_learning(
    input_data_path: str,
    output_data_path: str,
    best_model_path: str,
    best_model_params_path: str,
    max_epochs: int = 1000,
    patience: int = 50,
) -> dict:
    '''
    Train & evaluate model for machine learning based on given input and output datasets as well as best model structure and parameters
    '''
    try:
        schemas.TrainModelForMachineLearning(
            input_data_path=input_data_path,
            output_data_path=output_data_path,
            best_model_path=best_model_path,
            best_model_params_path=best_model_params_path,
            max_epochs=max_epochs,
            patience=patience,
        )
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = str(config.get_runs_dir())

        machine_learning_dir = os.path.join(runs_dir, 'machine_learning')
        os.makedirs(machine_learning_dir, exist_ok=True)

        ml_model_training_dir = os.path.join(machine_learning_dir, 'ml_model_training')
        os.makedirs(ml_model_training_dir, exist_ok=True)

        # Run model training
        from masgent.utils.ml_nn_train import train
        
        train(
            input_data=input_data_path,
            output_data=output_data_path,
            best_model_pkl=best_model_path,
            best_model_params=best_model_params_path,
            epochs=max_epochs,
            patience=patience,
            save_path=ml_model_training_dir,
            reset=True,
        )

        ml_files = list_files_in_dir(ml_model_training_dir)

        return {
            'status': 'success',
            'message': f'Completed model training for machine learning in {ml_model_training_dir}.',
            'ml_model_training_files': ml_files,
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Model training for machine learning failed: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Re-Train & evaluate model for machine learning',
    description='Re-Train model for machine learning based on given input and output datasets as well as old model structure and parameters',
    requires=['input_data_path', 'output_data_path', 'old_model_path', 'old_model_params_path'],
    optional=['max_epochs', 'patience'],
    defaults={'max_epochs': 1000, 'patience': 50},
    prereqs=[],
))
def retrain_model_for_machine_learning(
    input_data_path: str,
    output_data_path: str,
    old_model_path: str,
    old_model_params_path: str,
    max_epochs: int = 1000,
    patience: int = 50,
) -> dict:
    '''
    Re-Train & evaluate model for machine learning based on given input and output datasets as well as old model structure and parameters
    '''
    try:
        schemas.TrainModelForMachineLearning(
            input_data_path=input_data_path,
            output_data_path=output_data_path,
            best_model_path=old_model_path,
            best_model_params_path=old_model_params_path,
            max_epochs=max_epochs,
            patience=patience,
        )
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = str(config.get_runs_dir())

        machine_learning_dir = os.path.join(runs_dir, 'machine_learning')
        os.makedirs(machine_learning_dir, exist_ok=True)

        ml_model_retraining_dir = os.path.join(machine_learning_dir, 'ml_model_retraining')
        os.makedirs(ml_model_retraining_dir, exist_ok=True)

        # Run model training
        from masgent.utils.ml_nn_train import train
        
        train(
            input_data=input_data_path,
            output_data=output_data_path,
            best_model_pkl=old_model_path,
            best_model_params=old_model_params_path,
            epochs=max_epochs,
            patience=patience,
            save_path=ml_model_retraining_dir,
            reset=False,
        )

        ml_files = list_files_in_dir(ml_model_retraining_dir)

        return {
            'status': 'success',
            'message': f'Completed model training for machine learning in {ml_model_retraining_dir}.',
            'ml_model_retraining_files': ml_files,
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Model training for machine learning failed: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Pre-trained model prediction for Al-Mg-Si-Sc alloy',
    description='Make predictions of mechanical properties for Al-Mg-Si-Sc alloy using pre-trained machine learning model based on given Mg and Si contents',
    requires=['Mg', 'Si'],
    optional=[],
    defaults={},
    prereqs=[],
))
def model_prediction_for_AlMgSiSc(
        Mg: float,
        Si: float,
    ) -> dict:
    '''
    Make predictions of mechanical properties for Al-Mg-Si-Sc alloy using pre-trained machine learning model based on given Mg and Si contents
    '''
    try:
        schemas.ModelPredictionForAlMgSiSc(
            Mg=Mg,
            Si=Si,
        )
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = str(config.get_runs_dir())

        machine_learning_dir = os.path.join(runs_dir, 'machine_learning')
        os.makedirs(machine_learning_dir, exist_ok=True)

        ml_model_prediction_dir = os.path.join(machine_learning_dir, 'ml_model_prediction')
        os.makedirs(ml_model_prediction_dir, exist_ok=True)

        # Pre-trained model and scaler paths
        model_path = Path(__file__).resolve().parent.parent / 'res' / 'ml_nn_AlMgSiSc.pkl'
        x_scaler_path = Path(__file__).resolve().parent.parent / 'res' / 'ml_xs_AlMgSiSc.pkl'
        y_scaler_path = Path(__file__).resolve().parent.parent / 'res' / 'ml_ys_AlMgSiSc.pkl'
        predict_df_path = Path(__file__).resolve().parent.parent / 'res' / 'ml_db_AlMgSiSc.pkl'
        
        # Load the prediction dataframe
        with open(predict_df_path, 'rb') as f:
            predict_df = pickle.load(f)

        # Load the model and scalers
        model = torch.load(model_path, weights_only=False)
        x_scaler = pickle.load(open(x_scaler_path, 'rb'))
        y_scaler = pickle.load(open(y_scaler_path, 'rb'))

        # Based on the provided Mg and Si content, prepare the input features: PH_Al, PH_Eut, PH_AlSc2Si2, EL_Sc, EL_Si, EL_Mg
        EL_Mg = round(Mg / 100, 4)
        EL_Si = round(Si / 100, 4)
        
        # Find PH_Al, PH_Eut, PH_AlSc2Si2, EL_Sc based on EL_Mg and EL_Si
        df_filtered = predict_df[(predict_df['EL_Mg'] == EL_Mg) & (predict_df['EL_Si'] == EL_Si)]
        EL_Sc = df_filtered['EL_Sc'].values[0]
        EL_Al = 1 - EL_Si - EL_Mg - EL_Sc * 2
        PH_Al = df_filtered['PH_Al'].values[0]
        PH_Eut = df_filtered['PH_Eut'].values[0]
        PH_AlSc2Si2 = df_filtered['PH_AlSc2Si2'].values[0]

        # Scale input features
        x = df_filtered.loc[:, 'PH_Al':'EL_Mg'].to_numpy()
        x_std = x_scaler.transform(x)
        x_tensor = torch.tensor(x_std, dtype=torch.float32)

        # Predict
        with torch.no_grad():
            y_pred_std = model(x_tensor).numpy()
        
        # Inverse transform predictions
        y_pred = y_scaler.inverse_transform(y_pred_std).flatten()

        # Save results to txt
        with open(os.path.join(ml_model_prediction_dir, 'AlMgSiSc_prediction.txt'), 'w') as f:
            f.write(f'# Mechanical properties prediction for Al-Mg-Si-Sc alloy using pre-trained machine learning model by Masgent\n')
            f.write(f'\nInput Compositions:\n')
            f.write(f'Al: {EL_Al * 100:.2f} wt.%\n')
            f.write(f'Mg: {EL_Mg * 100:.2f} wt.%\n')
            f.write(f'Si: {EL_Si * 100:.2f} wt.%\n')
            f.write(f'Sc: {EL_Sc * 100:.2f} wt.%\n')
            f.write(f'\nCALPHAD Phase Fractions:\n')
            f.write(f'PH_Al: {PH_Al * 100:.2f} %\n')
            f.write(f'PH_Eut: {PH_Eut * 100:.2f} %\n')
            f.write(f'PH_AlSc2Si2: {PH_AlSc2Si2 * 100:.2f} %\n')
            f.write(f'\nPredicted Mechanical Properties:\n')
            f.write(f'Ultimate Tensile Strength (UTS): {y_pred[0]:.2f} MPa\n')
            f.write(f'Yield Strength (YS): {y_pred[1]:.2f} MPa\n')
            f.write(f'Elongation (EL): {y_pred[2]:.2f} %\n')

        return {
            'status': 'success',
            'message': f'Completed model prediction for Al-Mg-Si-Sc alloy in {ml_model_prediction_dir}.',
            'ml_AlMgSiSc_prediction_txt_path': os.path.join(ml_model_prediction_dir, 'ml_AlMgSiSc_prediction.txt'),
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Model prediction for Al-Mg-Si-Sc alloy failed: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Pre-trained model prediction for Al-Co-Cr-Fe-Ni high-entropy alloy',
    description='Make predictions of phase stability & elastic properties for Al-Co-Cr-Fe-Ni high-entropy alloy using pre-trained machine learning model based on given Al, Co, Cr, and Fe contents',
    requires=['Al', 'Co', 'Cr', 'Fe'],
    optional=[],
    defaults={},
    prereqs=[],
))
def model_prediction_for_AlCoCrFeNi(
        Al: float,
        Co: float,
        Cr: float,
        Fe: float
    ) -> dict:
    '''
    Make predictions of phase stability & elastic properties for Al-Co-Cr-Fe-Ni high-entropy alloy using pre-trained machine learning model based on given Al, Co, Cr, and Fe contents
    '''
    try:
        schemas.ModelPredictionForAlCoCrFeNi(
            Al=Al,
            Co=Co,
            Cr=Cr,
            Fe=Fe,
        )
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = str(config.get_runs_dir())

        machine_learning_dir = os.path.join(runs_dir, 'machine_learning')
        os.makedirs(machine_learning_dir, exist_ok=True)

        ml_model_prediction_dir = os.path.join(machine_learning_dir, 'ml_model_prediction')
        os.makedirs(ml_model_prediction_dir, exist_ok=True)

        # Pre-trained model and scaler paths
        model_path = Path(__file__).resolve().parent.parent / 'res' / 'ml_nn_AlCoCrFeNi.pkl'
        x_scaler_path = Path(__file__).resolve().parent.parent / 'res' / 'ml_xs_AlCoCrFeNi.pkl'
        y_scaler_path = Path(__file__).resolve().parent.parent / 'res' / 'ml_ys_AlCoCrFeNi.pkl'
        
        # Load the model and scalers
        model = torch.load(model_path, weights_only=False)
        x_scaler = pickle.load(open(x_scaler_path, 'rb'))
        y_scaler = pickle.load(open(y_scaler_path, 'rb'))

        # Scale input features
        Ni = 100 - Al - Co - Cr - Fe
        x = np.array([[Al / 100, Co / 100, Cr / 100, Fe / 100, Ni / 100]])
        x_std = x_scaler.transform(x)
        x_tensor = torch.tensor(x_std, dtype=torch.float32)

        # Predict
        with torch.no_grad():
            y_pred_std = model(x_tensor).numpy()
        
        # Inverse transform predictions
        y_pred = y_scaler.inverse_transform(y_pred_std).flatten()

        # Calculate elastic moduli from elastic constants
        from pymatgen.analysis.elasticity.elastic import ElasticTensor
        fcc_elastic_constants = np.array([[y_pred[2], y_pred[3], y_pred[3], 0, 0, 0],
                                        [y_pred[3], y_pred[2], y_pred[3], 0, 0, 0],
                                        [y_pred[3], y_pred[3], y_pred[2], 0, 0, 0],
                                        [0, 0, 0, y_pred[4], 0, 0],
                                        [0, 0, 0, 0, y_pred[4], 0],
                                        [0, 0, 0, 0, 0, y_pred[4]]])
        bcc_elastic_constants = np.array([[y_pred[5], y_pred[6], y_pred[6], 0, 0, 0],
                                        [y_pred[6], y_pred[5], y_pred[6], 0, 0, 0],
                                        [y_pred[6], y_pred[6], y_pred[5], 0, 0, 0],
                                        [0, 0, 0, y_pred[7], 0, 0],
                                        [0, 0, 0, 0, y_pred[7], 0],
                                        [0, 0, 0, 0, 0, y_pred[7]]])
        fcc_C = ElasticTensor.from_voigt(fcc_elastic_constants)
        bcc_C = ElasticTensor.from_voigt(bcc_elastic_constants)
        fcc_K_V = fcc_C.k_voigt
        fcc_K_R = fcc_C.k_reuss
        fcc_K_H = fcc_C.k_vrh
        fcc_G_V = fcc_C.g_voigt
        fcc_G_R = fcc_C.g_reuss
        fcc_G_H = fcc_C.g_vrh
        bcc_K_V = bcc_C.k_voigt
        bcc_K_R = bcc_C.k_reuss
        bcc_K_H = bcc_C.k_vrh
        bcc_G_V = bcc_C.g_voigt
        bcc_G_R = bcc_C.g_reuss
        bcc_G_H = bcc_C.g_vrh

        # Save results to txt
        with open(os.path.join(ml_model_prediction_dir, 'AlCoCrFeNi_prediction.txt'), 'w') as f:
            f.write(f'# Phase stability & elastic properties prediction for Al-Co-Cr-Fe-Ni high-entropy alloy using pre-trained machine learning model by Masgent\n')
            f.write(f'\nInput Compositions:\n')
            f.write(f'Al: {Al:.2f} at.%\n')
            f.write(f'Co: {Co:.2f} at.%\n')
            f.write(f'Cr: {Cr:.2f} at.%\n')
            f.write(f'Fe: {Fe:.2f} at.%\n')
            f.write(f'Ni: {Ni:.2f} at.%\n')
            f.write('\n------------------------------------------------------------\n')
            f.write(f'\nPredicted Phase Stability & Elastic Properties of FCC:\n')
            f.write(f'\nFormation Energy: {y_pred[0]:.2f} kJ/mol\n')
            f.write(f'\nElastic Constants (GPa):\n')
            for row in fcc_elastic_constants:
                f.write('\t'.join([f'{val:.2f}' for val in row]) + '\n')
            f.write(f'\nBulk Modulus (Voigt): {fcc_K_V:.2f} GPa\n')
            f.write(f'Bulk Modulus (Reuss): {fcc_K_R:.2f} GPa\n')
            f.write(f'Bulk Modulus (Hill): {fcc_K_H:.2f} GPa\n')
            f.write(f'\nShear Modulus (Voigt): {fcc_G_V:.2f} GPa\n')
            f.write(f'Shear Modulus (Reuss): {fcc_G_R:.2f} GPa\n')
            f.write(f'Shear Modulus (Hill): {fcc_G_H:.2f} GPa\n')
            f.write('\n------------------------------------------------------------\n')
            f.write(f'\nPredicted Phase Stability & Elastic Properties of BCC:\n')
            f.write(f'\nFormation Energy: {y_pred[1]:.2f} kJ/mol\n')
            f.write(f'\nElastic Constants (GPa):\n')
            for row in bcc_elastic_constants:
                f.write('\t'.join([f'{val:.2f}' for val in row]) + '\n')
            f.write(f'\nBulk Modulus (Voigt): {bcc_K_V:.2f} GPa\n')
            f.write(f'Bulk Modulus (Reuss): {bcc_K_R:.2f} GPa\n')
            f.write(f'Bulk Modulus (Hill): {bcc_K_H:.2f} GPa\n')
            f.write(f'\nShear Modulus (Voigt): {bcc_G_V:.2f} GPa\n')
            f.write(f'Shear Modulus (Reuss): {bcc_G_R:.2f} GPa\n')
            f.write(f'Shear Modulus (Hill): {bcc_G_H:.2f} GPa\n')

        return {
            'status': 'success',
            'message': f'Completed model prediction for Al-Co-Cr-Fe-Ni high-entropy alloy in {ml_model_prediction_dir}.',
            'ml_AlCoCrFeNi_prediction_txt_path': os.path.join(ml_model_prediction_dir, 'ml_AlCoCrFeNi_prediction.txt'),
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Model prediction for Al-Co-Cr-Fe-Ni high-entropy alloy failed: {str(e)}'
        }