#!/usr/bin/env python3

import os
import datetime
import random
import asyncio
from colorama import Fore, Style
from yaspin import yaspin
from yaspin.spinners import Spinners
from bullet import Bullet, colors

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolReturnPart,
    ToolCallPart,
)
from pydantic_ai import Agent

from masgent.cli_mode.cli_run import run_command
import masgent.tools as tools
from masgent.utils import (
    ask_for_api_key,
    color_print,
    color_input,
    start_new_session,
    print_help,
    exit_and_cleanup,
    clear_and_print_entry_message,
)
from masgent._config import config
from masgent.ai_mode.provider_factory import ProviderFactory
from masgent.ai_mode.prompts.assembler import PromptAssembler
from masgent.ai_mode.memory_manager import create_memory_processor, get_memory_manager

_provider = None


def print_entry_message():
    runs_dir = str(config.get_runs_dir())
    msg_1 = f"""
Welcome to Masgent AI —Your Materials Simulations Agent.
---------------------------------------------------------
Current Session Runs Directory: {runs_dir}
"""

    if _provider == "Masgent - Masgent AI":
        msg_2 = f"Provider: {_provider}\n\nNote: Initial response time may be up to one minute during cold start."
    else:
        msg_2 = f"Provider: {_provider}"

    msg_3 = """
Try asking:
  —"Generate a POSCAR file for NaCl."
  —"Prepare full VASP input files for LaCoO3."
  —"Add vacancy defects to a LiFePO4 crystal."
  —...
"""
    color_print(msg_1, "white")
    color_print(msg_2, "white")
    color_print(msg_3, "green")


def save_msg(msg, role, filename):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%-d %H:%M:%S")
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {role}:\n\n{msg}\n")
        f.write("\n" + "-" * 60 + "\n\n")




def _trim_message_history(messages, message_window):
    system_prompt = None
    system_prompt_index = None
    for i, msg in enumerate(messages):
        if isinstance(msg, ModelRequest) and any(
            isinstance(part, SystemPromptPart) for part in msg.parts
        ):
            system_prompt = msg
            system_prompt_index = i
            break

    target_cut = len(messages) - message_window
    for cut_index in range(target_cut, -1, -1):
        first_message = messages[cut_index]
        if any(isinstance(part, ToolReturnPart) for part in first_message.parts):
            continue
        if isinstance(first_message, ModelResponse) and any(
            isinstance(part, ToolCallPart) for part in first_message.parts
        ):
            continue
        result = messages[cut_index:]
        if system_prompt is not None and system_prompt_index is not None and cut_index > system_prompt_index:
            result = [system_prompt] + result
        return result
    return messages


async def chat_stream(agent, user_input: str, history: list):
    print("")
    with yaspin(Spinners.dots, text="Thinking...", color="cyan") as sp:
        async with agent.run_stream(user_prompt=user_input, message_history=history) as result:
            sp.hide()
            all_text = ""
            async for chunk in result.stream_text(delta=True):
                all_text += chunk
                print(Fore.GREEN + chunk + Style.RESET_ALL, end="", flush=True)
            print("")
        sp.stop()
        msg_path = str(config.get_runs_dir() / "conversation_history.txt")
        save_msg(all_text, "Masgent AI", filename=msg_path)
        return list(result.all_messages())


async def chat(agent, user_input: str, history: list):
    print("")
    with yaspin(Spinners.dots, text="Thinking...", color="cyan") as sp:
        result = await agent.run(user_prompt=user_input, message_history=history)
        sp.stop()
    text = result.output
    chunks = []
    split_points = sorted(random.sample(range(1, len(text)), k=min(10, len(text) // 10)))
    prev = 0
    for point in split_points:
        chunks.append(text[prev:point])
        prev = point
    chunks.append(text[prev:])
    for chunk in chunks:
        print(Fore.GREEN + chunk + Style.RESET_ALL, end="", flush=True)
        await asyncio.sleep(0.1)
    print("")
    msg_path = str(config.get_runs_dir() / "conversation_history.txt")
    save_msg(text, "Masgent AI", filename=msg_path)
    return list(result.all_messages())


async def ai_mode(agent):
    history = []
    msg_path = str(config.get_runs_dir() / "conversation_history.txt")
    with open(msg_path, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write(f'New AI Session Started at {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write("=" * 60 + "\n\n")
    try:
        while True:
            user_input = color_input(
                '\nAsk anything, or type "back" to return, "new" to start a new session > ',
                "yellow",
            ).strip()
            if not user_input:
                continue
            if user_input.lower() in {"new"}:
                start_new_session()
                os.system("cls" if os.name == "nt" else "clear")
                print_entry_message()
            elif user_input.lower() in {"back"}:
                return
            else:
                try:
                    save_msg(user_input, "User", filename=msg_path)
                    if _provider == "Masgent - Masgent AI":
                        history = await chat(agent, user_input, history)
                    else:
                        history = await chat_stream(agent, user_input, history)
                except Exception as e:
                    color_print(f"[Error]: {e}", "red")
    except (KeyboardInterrupt, EOFError):
        exit_and_cleanup()


def main():
    global _provider
    if not _provider:
        try:
            # Provider 名称映射
            provider_map = {
                "Masgent": "Masgent - Masgent AI",
                "OpenAI": "OpenAI - GPT-5 Nano",
                "Anthropic": "Anthropic - Claude Sonnet 4.5",
                "Google": "Google - Gemini 2.5 Flash",
                "xAI": "xAI - Grok 4.1 Fast",
                "Deepseek": "Deepseek - Deepseek Chat",
                "Alibaba": "Alibaba - Qwen Flash",
            }

            while True:
                clear_and_print_entry_message()
                choices = [
                    "Masgent    ->  Masgent AI (no API key needed, response time may be longer during cold start)",
                    "OpenAI     ->  GPT-5 Nano (requires OpenAI API key)",
                    "Anthropic  ->  Claude Sonnet 4.5 (requires Anthropic API key)",
                    "Google     ->  Gemini 2.5 Flash (requires Google API key)",
                    "xAI        ->  Grok 4.1 Fast (requires Grok API key)",
                    "Deepseek   ->  Deepseek Chat (requires Deepseek API key)",
                    "Alibaba    ->  Qwen Flash (requires Alibaba Cloud API key)",
                    "",
                    "New   ->  Start a new session",
                    "Back  ->  Return to previous menu",
                    "Main  ->  Return to main menu",
                    "Help  ->  Show available functions",
                    "Exit  ->  Quit the Masgent",
                ]
                cli = Bullet(
                    prompt="\n",
                    choices=choices,
                    margin=1,
                    bullet="*",
                    word_color=colors.foreground["green"],
                )
                user_input = cli.launch()

                if user_input.startswith("New"):
                    start_new_session()
                elif user_input.startswith("Back"):
                    return
                elif user_input.startswith("Main"):
                    run_command("0")
                elif user_input.startswith("Help"):
                    print_help()
                elif user_input.startswith("Exit"):
                    exit_and_cleanup()
                else:
                    # 匹配 provider
                    matched = None
                    for key, value in provider_map.items():
                        if user_input.startswith(key):
                            matched = value
                            break
                    if matched:
                        _provider = matched
                        break
                    else:
                        continue
        except (KeyboardInterrupt, EOFError):
            exit_and_cleanup()

    os.system("cls" if os.name == "nt" else "clear")
    print_entry_message()

    # 使用 ProviderFactory 创建模型
    try:
        model = ProviderFactory.create(_provider)
    except ValueError as e:
        color_print(f"[Error]: {e}", "red")
        exit_and_cleanup()

    system_prompt = PromptAssembler.quick_assemble(
        provider_name=_provider,
        max_tier="P2",
        session_context={
            "runs_dir": str(config.get_runs_dir()),
            "provider_name": _provider or "unknown",
        },
    )

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[
            tools.list_files,
            tools.rename_file,
            tools.read_file,
            tools.generate_vasp_poscar,
            tools.generate_vasp_inputs_from_poscar,
            tools.generate_vasp_inputs_hpc_slurm_script,
            tools.customize_vasp_kpoints_with_accuracy,
            tools.convert_structure_format,
            tools.convert_poscar_coordinates,
            tools.generate_vasp_poscar_with_vacancy_defects,
            tools.generate_vasp_poscar_with_substitution_defects,
            tools.generate_vasp_poscar_with_interstitial_defects,
            tools.generate_supercell_from_poscar,
            tools.generate_sqs_from_poscar,
            tools.generate_surface_slab_from_poscar,
            tools.generate_interface_from_poscars,
            tools.visualize_structure_from_poscar,
            tools.generate_vasp_workflow_of_convergence_tests,
            tools.generate_vasp_workflow_of_eos,
            tools.generate_vasp_workflow_of_elastic_constants,
            tools.generate_vasp_workflow_of_aimd,
            tools.generate_vasp_workflow_of_neb,
            tools.analyze_vasp_workflow_of_convergence_tests,
            tools.analyze_vasp_workflow_of_eos,
            tools.analyze_vasp_workflow_of_elastic_constants,
            tools.analyze_vasp_workflow_of_aimd,
            tools.run_simulation_using_mlps,
            tools.analyze_features_for_machine_learning,
            tools.reduce_dimensions_for_machine_learning,
            tools.augment_data_for_machine_learning,
            tools.design_model_for_machine_learning,
            tools.train_model_for_machine_learning,
            tools.retrain_model_for_machine_learning,
            tools.model_prediction_for_AlMgSiSc,
            tools.model_prediction_for_AlCoCrFeNi,
            tools.read_doc_file,
    ],
        history_processors=[create_memory_processor()],
    )

    mode = asyncio.run(ai_mode(agent))
    return mode


if __name__ == "__main__":
    main()
