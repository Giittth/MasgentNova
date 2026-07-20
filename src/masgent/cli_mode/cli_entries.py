"""
Masgent CLI 菜单入口模块

职责：
- 定义顶层菜单（command_0）和各级子菜单（command_1 ~ command_3_5）
- 使用 bullet_menu() 处理用户输入和全局命令（AI/New/Back/Main/Help/Exit）
- 根据用户选择调用 run_command() 执行对应的注册命令
"""

from bullet import Bullet, colors

from masgent.cli_mode.cli_run import register, run_command
from masgent.cli_mode import dft
from masgent.cli_mode import mlp
from masgent.cli_mode import ml
from masgent.utils import (
    print_help,
    global_commands,
    start_new_session,
    clear_and_print_entry_message,
    clear_and_print_banner_and_entry_message,
    exit_and_cleanup,
)
from masgent.cli_mode.base import bullet_menu


# 顶层主菜单（command_0）
@register('0', 'Entry point for Masgent CLI.')
def command_0():
    """
    主菜单入口，显示 Banner 并给出三大功能模块。
    用户选择 1/2/3 后路由到对应的子菜单。
    """
    try:
        while True:
            # 显示 Banner 和当前会话目录
            clear_and_print_banner_and_entry_message()

            choices = [
                '1. Density Functional Theory (DFT) Simulations',
                '2. Fast simulations using machine learning potentials (MLPs)',
                '3. Simple Machine Learning for Materials Science',
                '',
                'AI    ->  Chat with the Masgent AI',
                'New   ->  Start a new session',
                'Help  ->  Show available functions',
                'Exit  ->  Quit the Masgent',
            ]

            cli = Bullet(
                prompt='\n',
                choices=choices,
                margin=1,
                bullet=' ●',
                word_color=colors.foreground['green'],
            )
            user_input = cli.launch()

            # 处理全局命令（AI/New/Help/Exit）
            if user_input.startswith('AI'):
                from masgent.ai_mode import ai_backend
                ai_backend.main()
            elif user_input.startswith('New'):
                start_new_session()
            elif user_input.startswith('Help'):
                print_help()
            elif user_input.startswith('Exit'):
                exit_and_cleanup()
            # 路由到子菜单
            elif user_input.startswith('1'):
                run_command('1')
            elif user_input.startswith('2'):
                run_command('2')
            elif user_input.startswith('3'):
                run_command('3')
            else:
                continue  # 无效输入，重新循环

    except (KeyboardInterrupt, EOFError):
        exit_and_cleanup()


# 一级子菜单：DFT 仿真（command_1）
@register('1', 'Density Functional Theory (DFT) Simulations.')
def command_1():
    """
    DFT 模块菜单，列出四个子类别。
    使用 bullet_menu() 统一处理菜单和全局命令。
    """
    choices = [
        '1.1 Structure Preparation & Manipulation',
        '1.2 VASP Input File Preparation',
        '1.3 Standard VASP Workflow Preparation',
        '1.4 Standard VASP Workflow Output Analysis',
    ]
    # bullet_menu 会处理 AI/New/Back/Main/Help/Exit，返回用户选择的具体选项或 None
    user_input = bullet_menu(choices, title='\nDFT Simulations:')
    if user_input is None:  # 用户选择了 Back
        return

    # 将用户选择映射到对应的子命令代码
    code_map = {
        '1.1 Structure Preparation & Manipulation': '1.1',
        '1.2 VASP Input File Preparation': '1.2',
        '1.3 Standard VASP Workflow Preparation': '1.3',
        '1.4 Standard VASP Workflow Output Analysis': '1.4',
    }
    run_command(code_map[user_input])


# 二级子菜单：结构准备与操作（command_1_1）
@register('1.1', 'Structure Preparation & Manipulation.')
def command_1_1():
    """
    结构操作菜单，包含生成 POSCAR、缺陷、超胞、SQS、表面、界面、可视化等。
    """
    choices = [
        '1.1.1 Generate POSCAR from chemical formula',
        '1.1.2 Convert POSCAR coordinates (Direct <-> Cartesian)',
        '1.1.3 Convert structure file formats (CIF, POSCAR, XYZ)',
        '1.1.4 Generate structures with defects (Vacancies, Substitutions, Interstitials)',
        '1.1.5 Generate supercells',
        '1.1.6 Generate Special Quasirandom Structures (SQS)',
        '1.1.7 Generate surface slabs',
        '1.1.8 Generate interface structures',
        '1.1.9 Visualize structure',
    ]
    user_input = bullet_menu(choices, title='\nStructure Preparation & Manipulation:')
    if user_input is None:
        return

    code_map = {
        '1.1.1 Generate POSCAR from chemical formula': '1.1.1',
        '1.1.2 Convert POSCAR coordinates (Direct <-> Cartesian)': '1.1.2',
        '1.1.3 Convert structure file formats (CIF, POSCAR, XYZ)': '1.1.3',
        '1.1.4 Generate structures with defects (Vacancies, Substitutions, Interstitials)': '1.1.4',
        '1.1.5 Generate supercells': '1.1.5',
        '1.1.6 Generate Special Quasirandom Structures (SQS)': '1.1.6',
        '1.1.7 Generate surface slabs': '1.1.7',
        '1.1.8 Generate interface structures': '1.1.8',
        '1.1.9 Visualize structure': '1.1.9',
    }
    run_command(code_map[user_input])


# 二级子菜单：VASP 输入文件准备（command_1_2）
@register('1.2', 'VASP Input File Preparation')
def command_1_2():
    """
    VASP 输入文件准备菜单，包括全套输入、INCAR 模板、KPOINTS、HPC 脚本。
    """
    choices = [
        '1.2.1 Prepare full VASP input files (INCAR, KPOINTS, POTCAR, POSCAR)',
        '1.2.2 Generate INCAR templates (relaxation, static, etc.)',
        '1.2.3 Generate KPOINTS with specified accuracy',
        '1.2.4 Generate HPC job submission script',
    ]
    user_input = bullet_menu(choices, title='\nVASP Input File Preparation:')
    if user_input is None:
        return

    code_map = {
        '1.2.1 Prepare full VASP input files (INCAR, KPOINTS, POTCAR, POSCAR)': '1.2.1',
        '1.2.2 Generate INCAR templates (relaxation, static, etc.)': '1.2.2',
        '1.2.3 Generate KPOINTS with specified accuracy': '1.2.3',
        '1.2.4 Generate HPC job submission script': '1.2.4',
    }
    run_command(code_map[user_input])


# 二级子菜单：标准 VASP 工作流准备（command_1_3）
@register('1.3', 'Standard VASP Workflows.')
def command_1_3():
    """
    标准 VASP 工作流准备菜单：收敛测试、EOS、弹性常数、AIMD、NEB。
    """
    choices = [
        '1.3.1 Convergence testing (ENCUT, KPOINTS)',
        '1.3.2 Equation of State (EOS)',
        '1.3.3 Elastic constants calculations',
        '1.3.4 Ab-initio Molecular Dynamics (AIMD)',
        '1.3.5 Nudged Elastic Band (NEB) calculations',
    ]
    user_input = bullet_menu(choices, title='\nStandard VASP Workflows:')
    if user_input is None:
        return

    code_map = {
        '1.3.1 Convergence testing (ENCUT, KPOINTS)': '1.3.1',
        '1.3.2 Equation of State (EOS)': '1.3.2',
        '1.3.3 Elastic constants calculations': '1.3.3',
        '1.3.4 Ab-initio Molecular Dynamics (AIMD)': '1.3.4',
        '1.3.5 Nudged Elastic Band (NEB) calculations': '1.3.5',
    }
    run_command(code_map[user_input])


# 二级子菜单：VASP 输出分析（command_1_4）
@register('1.4', 'VASP Output Analysis')
def command_1_4():
    """
    VASP 工作流结果分析菜单：收敛测试、EOS、弹性常数、AIMD、NEB 的后处理。
    """
    choices = [
        '1.4.1 Convergence test analysis',
        '1.4.2 Equation of State (EOS) analysis',
        '1.4.3 Elastic constants analysis',
        '1.4.4 Ab-initio Molecular Dynamics (AIMD) analysis',
        '1.4.5 Nudged Elastic Band (NEB) analysis',
    ]
    user_input = bullet_menu(choices, title='\nVASP Output Analysis:')
    if user_input is None:
        return

    code_map = {
        '1.4.1 Convergence test analysis': '1.4.1',
        '1.4.2 Equation of State (EOS) analysis': '1.4.2',
        '1.4.3 Elastic constants analysis': '1.4.3',
        '1.4.4 Ab-initio Molecular Dynamics (AIMD) analysis': '1.4.4',
        '1.4.5 Nudged Elastic Band (NEB) analysis': '1.4.5',
    }
    run_command(code_map[user_input])


# 一级子菜单：MLP 模拟（command_2）
@register('2', 'Fast Simulations Using Machine Learning Potentials (MLPs).')
def command_2():
    """
    MLP 模拟菜单，列出支持的四种 MLP 模型。
    """
    choices = [
        '2.1 SevenNet',
        '2.2 CHGNet',
        '2.3 Orb-v3',
        '2.4 MatterSim',
    ]
    user_input = bullet_menu(choices, title='\nMachine Learning Potentials:')
    if user_input is None:
        return

    code_map = {
        '2.1 SevenNet': '2.1',
        '2.2 CHGNet': '2.2',
        '2.3 Orb-v3': '2.3',
        '2.4 MatterSim': '2.4',
    }
    run_command(code_map[user_input])


# 一级子菜单：机器学习（command_3）
@register('3', 'Simple Machine Learning for Materials Science.')
def command_3():
    """
    机器学习主菜单，涵盖数据准备、模型设计、训练、评估、预训练应用。
    """
    choices = [
        '3.1 Dataset Preparation & Visualization',
        '3.2 Model Design & Hyperparameter Tuning',
        '3.3 Model Training & Evaluation',
        '3.4 Model Retraining with New Data',
        '3.5 Pre-trained Model Applications',
    ]
    user_input = bullet_menu(choices, title='\nMachine Learning for Materials:')
    if user_input is None:
        return

    code_map = {
        '3.1 Dataset Preparation & Visualization': '3.1',
        '3.2 Model Design & Hyperparameter Tuning': '3.2',
        '3.3 Model Training & Evaluation': '3.3',
        '3.4 Model Retraining with New Data': '3.4',
        '3.5 Pre-trained Model Applications': '3.5',
    }
    run_command(code_map[user_input])


# 二级子菜单：数据准备与特征分析（command_3_1）
@register('3.1', 'Data Preparation & Feature Analysis')
def command_3_1():
    """
    数据准备子菜单：特征分析、降维、数据增强。
    """
    choices = [
        '3.1.1 Feature analysis and visualization',
        '3.1.2 Dimensionality reduction (if too many features)',
        '3.1.3 Data augmentation (if limited data)',
    ]
    user_input = bullet_menu(choices, title='\nData Preparation & Feature Analysis:')
    if user_input is None:
        return

    code_map = {
        '3.1.1 Feature analysis and visualization': '3.1.1',
        '3.1.2 Dimensionality reduction (if too many features)': '3.1.2',
        '3.1.3 Data augmentation (if limited data)': '3.1.3',
    }
    run_command(code_map[user_input])


# 二级子菜单：预训练模型应用（command_3_5）
@register('3.5', 'Pre-trained Model Applications')
def command_3_5():
    """
    预训练模型应用菜单：两个具体合金体系的性质预测。
    """
    choices = [
        '3.5.1 Mechanical Properties Prediction in Sc-modified Al-Mg-Si Alloys',
        '3.5.2 Phase Stability & Elastic Properties Prediction in Al-Co-Cr-Fe-Ni High-Entropy Alloys',
    ]
    user_input = bullet_menu(choices, title='\nPre-trained Model Applications:')
    if user_input is None:
        return

    code_map = {
        '3.5.1 Mechanical Properties Prediction in Sc-modified Al-Mg-Si Alloys': '3.5.1',
        '3.5.2 Phase Stability & Elastic Properties Prediction in Al-Co-Cr-Fe-Ni High-Entropy Alloys': '3.5.2',
    }
    run_command(code_map[user_input])