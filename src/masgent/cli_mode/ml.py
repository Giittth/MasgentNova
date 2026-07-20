"""机器学习相关命令（3.x 系列）"""

import os
import time

import masgent.tools as tools
from masgent.cli_mode.base import bullet_menu, handle_keyboard_interrupt
from masgent.cli_mode.cli_run import register
from masgent.utils import color_input, color_print
from masgent.models import schemas
from masgent._config import config


@register('3.1.1', 'Feature analysis and visualization')
@handle_keyboard_interrupt
def command_3_1_1():
    while True:
        input_data_path = color_input('\nEnter the path to the input feature data file (CSV): ', 'yellow').strip()
        if not input_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=input_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {input_data_path}, please double check and try again.\n', 'red')

    while True:
        output_data_path = color_input('\nEnter the path to the output feature data file (CSV): ', 'yellow').strip()
        if not output_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=output_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {output_data_path}, please double check and try again.\n', 'red')

    result = tools.analyze_features_for_machine_learning(input_data_path=input_data_path, output_data_path=output_data_path)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('3.1.2', 'Dimensionality reduction (if too many features)')
@handle_keyboard_interrupt
def command_3_1_2():
    while True:
        input_data_path = color_input('\nEnter the path to the input feature data file (CSV): ', 'yellow').strip()
        if not input_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=input_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {input_data_path}, please double check and try again.\n', 'red')

    while True:
        n_components_str = color_input('\nEnter the number of principal components to reduce to (e.g., 2): ', 'yellow').strip()
        if not n_components_str:
            continue
        try:
            n_components = int(n_components_str)
            schemas.ReduceDimensionsForMachineLearning(input_data_path=input_data_path, n_components=n_components)
            break
        except Exception:
            color_print(f'[Error] Invalid number of components: {n_components_str}, please double check and try again.\n', 'red')

    result = tools.reduce_dimensions_for_machine_learning(input_data_path=input_data_path, n_components=n_components)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('3.1.3', 'Data augmentation (if limited data)')
@handle_keyboard_interrupt
def command_3_1_3():
    while True:
        input_data_path = color_input('\nEnter the path to the input feature data file (CSV): ', 'yellow').strip()
        if not input_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=input_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {input_data_path}, please double check and try again.\n', 'red')

    while True:
        output_data_path = color_input('\nEnter the path to the output feature data file (CSV): ', 'yellow').strip()
        if not output_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=output_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {output_data_path}, please double check and try again.\n', 'red')

    while True:
        num_augmentations_str = color_input('\nEnter the number of augmentations to perform (e.g., 100): ', 'yellow').strip()
        if not num_augmentations_str:
            continue
        try:
            num_augmentations = int(num_augmentations_str)
            schemas.AugmentDataForMachineLearning(
                input_data_path=input_data_path,
                output_data_path=output_data_path,
                num_augmentations=num_augmentations,
            )
            break
        except Exception:
            color_print(f'[Error] Invalid number of augmentations: {num_augmentations_str}, please double check and try again.\n', 'red')

    result = tools.augment_data_for_machine_learning(
        input_data_path=input_data_path,
        output_data_path=output_data_path,
        num_augmentations=num_augmentations,
    )
    color_print(result['message'], 'green')
    time.sleep(3)


@register('3.2', 'Model Design & Hyperparameter Tuning')
@handle_keyboard_interrupt
def command_3_2():
    while True:
        input_data_path = color_input('\nEnter the path to the input feature data file (CSV): ', 'yellow').strip()
        if not input_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=input_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {input_data_path}, please double check and try again.\n', 'red')

    while True:
        output_data_path = color_input('\nEnter the path to the output feature data file (CSV): ', 'yellow').strip()
        if not output_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=output_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {output_data_path}, please double check and try again.\n', 'red')

    while True:
        num_trials_str = color_input('\nEnter the number of hyperparameter tuning trials (e.g., 50): ', 'yellow').strip()
        if not num_trials_str:
            continue
        try:
            num_trials = int(num_trials_str)
            schemas.DesignModelForMachineLearning(
                input_data_path=input_data_path,
                output_data_path=output_data_path,
                n_trials=num_trials,
            )
            break
        except Exception:
            color_print(f'[Error] Invalid number of trials: {num_trials_str}, please double check and try again.\n', 'red')

    result = tools.design_model_for_machine_learning(
        input_data_path=input_data_path,
        output_data_path=output_data_path,
        n_trials=num_trials,
    )
    color_print(result['message'], 'green')
    time.sleep(3)


@register('3.3', 'Model Training & Evaluation')
@handle_keyboard_interrupt
def command_3_3():
    while True:
        input_data_path = color_input('\nEnter the path to the input feature data file (CSV): ', 'yellow').strip()
        if not input_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=input_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {input_data_path}, please double check and try again.\n', 'red')

    while True:
        output_data_path = color_input('\nEnter the path to the output feature data file (CSV): ', 'yellow').strip()
        if not output_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=output_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {output_data_path}, please double check and try again.\n', 'red')

    while True:
        best_model_path = color_input('\nEnter the path to the best model file from model design (e.g., best_model.pkl): ', 'yellow').strip()
        if not best_model_path:
            continue
        try:
            schemas.CheckPklFile(file_path=best_model_path)
            break
        except Exception:
            color_print(f'[Error] Invalid model file: {best_model_path}, please double check and try again.\n', 'red')

    while True:
        best_model_params_path = color_input('\nEnter the path to the best model hyperparameters file from model design (e.g., best_model_params.log): ', 'yellow').strip()
        if not best_model_params_path:
            continue
        try:
            schemas.CheckLogFile(file_path=best_model_params_path)
            break
        except Exception:
            color_print(f'[Error] Invalid hyperparameters file: {best_model_params_path}, please double check and try again.\n', 'red')

    while True:
        max_epochs_str = color_input('\nEnter the maximum number of training epochs (e.g., 1000): ', 'yellow').strip()
        if not max_epochs_str:
            continue
        try:
            max_epochs = int(max_epochs_str)
            schemas.TrainModelForMachineLearning(
                input_data_path=input_data_path,
                output_data_path=output_data_path,
                best_model_path=best_model_path,
                best_model_params_path=best_model_params_path,
                max_epochs=max_epochs,
            )
            break
        except Exception:
            color_print(f'[Error] Invalid maximum epochs: {max_epochs_str}, please double check and try again.\n', 'red')

    while True:
        patience_str = color_input('\nEnter the early stopping patience (number of epochs with no improvement) (e.g., 50): ', 'yellow').strip()
        if not patience_str:
            continue
        try:
            patience = int(patience_str)
            schemas.TrainModelForMachineLearning(
                input_data_path=input_data_path,
                output_data_path=output_data_path,
                best_model_path=best_model_path,
                best_model_params_path=best_model_params_path,
                max_epochs=max_epochs,
                patience=patience,
            )
            break
        except Exception:
            color_print(f'[Error] Invalid patience: {patience_str}, please double check and try again.\n', 'red')

    result = tools.train_model_for_machine_learning(
        input_data_path=input_data_path,
        output_data_path=output_data_path,
        best_model_path=best_model_path,
        best_model_params_path=best_model_params_path,
        max_epochs=max_epochs,
        patience=patience,
    )
    color_print(result['message'], 'green')
    time.sleep(3)


@register('3.4', 'Model Re-Training & Evaluation')
@handle_keyboard_interrupt
def command_3_4():
    while True:
        input_data_path = color_input('\nEnter the path to the input feature data file with new data (CSV): ', 'yellow').strip()
        if not input_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=input_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {input_data_path}, please double check and try again.\n', 'red')

    while True:
        output_data_path = color_input('\nEnter the path to the output feature data file with new data (CSV): ', 'yellow').strip()
        if not output_data_path:
            continue
        try:
            schemas.CheckCSVFile(file_path=output_data_path)
            break
        except Exception:
            color_print(f'[Error] Invalid CSV file: {output_data_path}, please double check and try again.\n', 'red')

    while True:
        old_model_path = color_input('\nEnter the path to the old model file (PKL): ', 'yellow').strip()
        if not old_model_path:
            continue
        try:
            schemas.CheckPklFile(file_path=old_model_path)
            break
        except Exception:
            color_print(f'[Error] Invalid model file: {old_model_path}, please double check and try again.\n', 'red')

    while True:
        old_model_params_path = color_input('\nEnter the path to the old model hyperparameters file (LOG): ', 'yellow').strip()
        if not old_model_params_path:
            continue
        try:
            schemas.CheckLogFile(file_path=old_model_params_path)
            break
        except Exception:
            color_print(f'[Error] Invalid hyperparameters file: {old_model_params_path}, please double check and try again.\n', 'red')

    while True:
        max_epochs_str = color_input('\nEnter the maximum number of training epochs (e.g., 1000): ', 'yellow').strip()
        if not max_epochs_str:
            continue
        try:
            max_epochs = int(max_epochs_str)
            schemas.TrainModelForMachineLearning(
                input_data_path=input_data_path,
                output_data_path=output_data_path,
                best_model_path=old_model_path,
                best_model_params_path=old_model_params_path,
                max_epochs=max_epochs,
            )
            break
        except Exception:
            color_print(f'[Error] Invalid maximum epochs: {max_epochs_str}, please double check and try again.\n', 'red')

    while True:
        patience_str = color_input('\nEnter the early stopping patience (number of epochs with no improvement) (e.g., 50): ', 'yellow').strip()
        if not patience_str:
            continue
        try:
            patience = int(patience_str)
            schemas.TrainModelForMachineLearning(
                input_data_path=input_data_path,
                output_data_path=output_data_path,
                best_model_path=old_model_path,
                best_model_params_path=old_model_params_path,
                max_epochs=max_epochs,
                patience=patience,
            )
            break
        except Exception:
            color_print(f'[Error] Invalid patience: {patience_str}, please double check and try again.\n', 'red')

    result = tools.retrain_model_for_machine_learning(
        input_data_path=input_data_path,
        output_data_path=output_data_path,
        old_model_path=old_model_path,
        old_model_params_path=old_model_params_path,
        max_epochs=max_epochs,
        patience=patience,
    )
    color_print(result['message'], 'green')
    time.sleep(3)


@register('3.5.1', 'Mechanical Properties Prediction in Sc-modified Al-Mg-Si Alloys')
@handle_keyboard_interrupt
def command_3_5_1():
    while True:
        Mg_Si_str = color_input('\nEnter the Mg (0.00-0.70 wt.%) and Si (4.00-13.00 wt.%) content (e.g., 0.50 5.00): ', 'yellow').strip()
        if not Mg_Si_str:
            continue
        try:
            Mg, Si = [float(x) for x in Mg_Si_str.split()]
            schemas.ModelPredictionForAlMgSiSc(Mg=Mg, Si=Si)
            break
        except Exception:
            color_print(f'[Error] Invalid Mg and Si content: {Mg_Si_str}, please double check and try again.\n', 'red')

    result = tools.model_prediction_for_AlMgSiSc(Mg=Mg, Si=Si)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('3.5.2', 'Phase Stability & Elastic Properties Prediction in Al-Co-Cr-Fe-Ni High-Entropy Alloys')
@handle_keyboard_interrupt
def command_3_5_2():
    while True:
        elements_str = color_input('\nEnter the atomic percentages of Al, Co, Cr, and Fe (e.g., 20.0 20.0 20.0 20.0): ', 'yellow').strip()
        if not elements_str:
            continue
        try:
            Al, Co, Cr, Fe = [float(x) for x in elements_str.split()]
            schemas.ModelPredictionForAlCoCrFeNi(Al=Al, Co=Co, Cr=Cr, Fe=Fe)
            break
        except Exception:
            color_print(f'[Error] Invalid atomic percentages: {elements_str}, please double check and try again.\n', 'red')

    result = tools.model_prediction_for_AlCoCrFeNi(Al=Al, Co=Co, Cr=Cr, Fe=Fe)
    color_print(result['message'], 'green')
    time.sleep(3)