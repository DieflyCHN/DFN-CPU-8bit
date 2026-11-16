#!/usr/bin/env python3
from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

VERSION = "v0.2"
RAM_SIZE = 0x1000  # 12 位字地址，4096 x 16 bits = 8 KiB
WORD_MASK = 0xFFFF
HLT_WORD = 0xC000
WORDS_PER_ROW = 16
REGS = {f"R{i}": i for i in range(4)}
ALU_OPS = {"ADD": 0, "SUB": 1, "AND": 2, "OR": 3}


@dataclass(frozen=True)
class Instruction:
    word: int
    source: str


def parse_reg(token: str) -> int:
    token = token.upper().strip()
    if token not in REGS:
        raise ValueError(f"未知寄存器：{token}，请使用 R0–R3")
    return REGS[token]


def parse_number(token: str, minimum: int, maximum: int, name: str) -> int:
    try:
        value = int(token, 0)
    except ValueError:
        raise ValueError(f"{name}格式错误：{token}；十六进制请加 0x 前缀") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{name}超出范围：{token}（{minimum}–{maximum}）")
    return value


def parse_imm8(token: str) -> int:
    return parse_number(token, -128, 255, "立即数") & 0xFF


def clean_line(line: str) -> str:
    for mark in (";", "#"):
        line = line.split(mark, 1)[0]
    return line.strip()


def assemble_line(line: str) -> int:
    parts = shlex.split(clean_line(line).replace(",", " "))
    if not parts:
        raise ValueError("空指令")
    op = parts[0].upper()

    def operands(count: int, syntax: str) -> None:
        if len(parts) != count + 1:
            raise ValueError(f"用法：{syntax}")

    if op == "HLT":
        operands(0, "HLT")
        return HLT_WORD
    if op == "JMP":
        operands(1, "JMP Addr（0x000–0xFFF）")
        return 0xD000 | parse_number(parts[1], 0, RAM_SIZE - 1, "跳转地址")
    if op == "NOP" and len(parts) == 1:
        return 0x8000
    if op in ("READ", "NOP"):
        operands(2, f"{op} Ra, Rb")
        return 0x8000 | (parse_reg(parts[1]) << 8) | (parse_reg(parts[2]) << 6)
    if op == "LDI":
        operands(2, "LDI Rd, imm8")
        return 0x4000 | (parse_reg(parts[1]) << 10) | parse_imm8(parts[2])
    if op == "MOV":
        operands(2, "MOV Rd, Rs")
        rd, rs = parse_reg(parts[1]), parse_reg(parts[2])
        return 0x3000 | (rd << 10) | (rs << 8) | (rs << 6)
    if op in ALU_OPS:
        operands(3, f"{op} Rd, Ra, Rb")
        rd, ra, rb = (parse_reg(token) for token in parts[1:])
        return (ALU_OPS[op] << 12) | (rd << 10) | (ra << 8) | (rb << 6)
    if op in (".WORD", "WORD"):
        operands(1, "WORD 0x1234")
        return parse_number(parts[1], 0, WORD_MASK, "机器码")
    raise ValueError(f"未知指令：{op}")


def word_to_asm_hint(word: int) -> str:
    typ = (word >> 14) & 3
    op = (word >> 12) & 3
    wa, ra, rb = (word >> 10) & 3, (word >> 8) & 3, (word >> 6) & 3
    if typ == 0:
        name = ("ADD", "SUB", "AND", "OR")[op]
        hint = f"{name} R{wa}, R{ra}, R{rb}"
    elif typ == 1:
        hint = f"LDI R{wa}, {word & 0xFF}"
    elif typ == 2:
        hint = "NOP" if word == 0x8000 else f"READ R{ra}, R{rb}"
    elif op == 0:
        hint = "HLT"
    elif op == 1:
        hint = f"JMP 0x{word & 0xFFF:03X}"
    else:
        return f"WORD 0x{word:04X}"
    # 非标准编码及未实现指令保留为 WORD，确保显示内容可还原原机器码。
    return hint if assemble_line(hint) == word else f"WORD 0x{word:04X}"


def format_instruction(addr: int, instruction: Instruction) -> str:
    bits = f"{instruction.word:016b}"
    grouped = " ".join(bits[i:i + 4] for i in range(0, 16, 4))
    return f"0x{addr:03X} {grouped}  # {instruction.word:04X}  {instruction.source}"


def render_listing(program: list[Instruction]) -> str:
    if len(program) > RAM_SIZE:
        raise ValueError(f"程序过大：{len(program)} > {RAM_SIZE} 字")
    if any(not 0 <= item.word <= WORD_MASK for item in program):
        raise ValueError("机器码必须在 0x0000–0xFFFF 范围内")
    lines = [
        f"# DFN-CPU ROM Writer {VERSION} | CPU v0.2",
        f"# RAM: 0x000–0xFFF，4096 x 16 bits；程序：{len(program)} 字",
        "# 汇编列表：地址 / 二进制 / 机器码 / 汇编",
    ]
    lines.extend(format_instruction(addr, item) for addr, item in enumerate(program))
    lines.extend(["", "# RAM 复制区（制表符分隔，每行 16 字；末行补 HLT = 0xC000）"])
    words = [item.word for item in program]
    padded_size = max(WORDS_PER_ROW, ((len(words) + WORDS_PER_ROW - 1) // WORDS_PER_ROW) * WORDS_PER_ROW)
    words.extend([HLT_WORD] * (padded_size - len(words)))
    for addr in range(0, len(words), WORDS_PER_ROW):
        lines.append("\t".join([f"0x{addr:03X}"] + [
            f"0x{word:04X}" for word in words[addr:addr + WORDS_PER_ROW]
        ]))
    return "\n".join(lines) + "\n"


def save_listing(program: list[Instruction], path: str | Path) -> None:
    Path(path).write_text(render_listing(program), encoding="utf-8")


def print_help() -> None:
    print(
        "\n汇编指令（Rd 为目标寄存器，Ra、Rb、Rs 为源寄存器）：\n"
        "  LDI  Rd, 数值      将立即数写入 Rd，范围 -128–255\n"
        "  ADD  Rd, Ra, Rb    加法：Rd = Ra + Rb\n"
        "  SUB  Rd, Ra, Rb    减法：Rd = Ra - Rb\n"
        "  AND  Rd, Ra, Rb    按位与：Rd = Ra & Rb\n"
        "  OR   Rd, Ra, Rb    按位或：Rd = Ra | Rb\n"
        "  MOV  Rd, Rs        复制：Rd = Rs（使用 OR 实现）\n"
        "  READ Ra, Rb        读取两个寄存器\n"
        "  JMP  地址          跳转到指定字地址，范围 0x000–0xFFF\n"
        "  NOP               空操作\n"
        "  HLT               停机\n"
        "  WORD 0x1234       直接写入一个 16 位机器码\n"
        "\n输入规则：\n"
        "  寄存器为 R0–R3；数值支持十进制、0x 十六进制、0b 二进制。\n"
        "  大小写不限，逗号可省略；; 或 # 后为注释。提示符显示下一条指令地址。\n"
        "\n交互命令：\n"
        "  /start            清空程序，从 0x000 重新编写\n"
        "  /show             查看当前汇编列表\n"
        "  /delete           删除最后一条指令\n"
        "  /save [文件名]    保存 .lst，默认 program.lst；含空格的路径请加双引号\n"
        "                    文件尾部附 RAM 复制区，每行 16 字，末行补 HLT\n"
        "  /help             显示此说明\n"
        "  /exit             退出\n"
    )


def repl() -> None:
    program: list[Instruction] = []
    print(f"DFN-CPU ROM Writer {VERSION} | RAM 0x000–0xFFF（4096 字）")
    print_help()
    while True:
        prompt = f"0x{len(program):03X}> " if len(program) < RAM_SIZE else "RAM已满> "
        try:
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        try:
            if raw.startswith("/"):
                parts = shlex.split(raw)
                cmd, args = parts[0].lower(), parts[1:]
                if cmd == "/save":
                    if len(args) > 1:
                        raise ValueError('用法：/save [文件名]；含空格的路径请加双引号')
                    path = Path(args[0] if args else "program.lst").with_suffix(".lst")
                    save_listing(program, path)
                    print(f"已保存：{path}（{len(program)} 条指令，含 RAM 复制区）")
                elif args:
                    raise ValueError(f"{cmd} 不接受参数")
                elif cmd == "/start":
                    program.clear()
                    print("已清空，下条地址：0x000")
                elif cmd == "/show":
                    if not program:
                        print("（空程序）")
                    for addr, item in enumerate(program):
                        print(format_instruction(addr, item))
                elif cmd == "/delete":
                    if program:
                        item = program.pop()
                        print(f"已删除：{format_instruction(len(program), item)}")
                    else:
                        print("没有可删除的指令")
                elif cmd == "/help":
                    print_help()
                elif cmd == "/exit":
                    break
                else:
                    raise ValueError(f"未知命令：{cmd}")
                continue
            source = clean_line(raw)
            if not source:
                continue
            if len(program) >= RAM_SIZE:
                raise ValueError("RAM 已满（4096 字），请使用 /delete 或 /start")
            word = assemble_line(source)
            item = Instruction(word, source)
            addr = len(program)
            program.append(item)
            print(f"=> {format_instruction(addr, item)}")
        except (ValueError, OSError) as exc:
            print(f"错误：{exc}")


if __name__ == "__main__":
    repl()
