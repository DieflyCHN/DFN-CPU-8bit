import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "rom_writer_v02", Path(__file__).with_name("rom_writer_v0.2.py")
)
writer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = writer
spec.loader.exec_module(writer)


def instructions(*sources):
    return [writer.Instruction(writer.assemble_line(src), src) for src in sources]


def run_repl(lines):
    output = io.StringIO()
    with patch("builtins.input", side_effect=lines), contextlib.redirect_stdout(output):
        writer.repl()
    return output.getvalue()


class AssemblerTests(unittest.TestCase):
    def test_isa_fibonacci(self):
        source = ["LDI R0, 0", "LDI R1, 1", "LDI R2, 0", "LDI R3, 0",
                  "ADD R2, R0, R1", "MOV R0, R1", "MOV R1, R2",
                  "READ R2, R3", "JMP 0x004"]
        self.assertEqual([writer.assemble_line(src) for src in source],
                         [0x4000, 0x4401, 0x4800, 0x4C00, 0x0840,
                          0x3140, 0x3680, 0x82C0, 0xD004])

    def test_mov_all_registers_and_alu(self):
        for rd in range(4):
            for rs in range(4):
                self.assertEqual(writer.assemble_line(f"MOV R{rd}, R{rs}"),
                                 writer.assemble_line(f"OR R{rd}, R{rs}, R{rs}"))
        for op, expected in [("ADD", 0x09C0), ("SUB", 0x19C0),
                             ("AND", 0x29C0), ("OR", 0x39C0)]:
            self.assertEqual(writer.assemble_line(f"{op} R2, R1, R3"), expected)

    def test_numbers_comments_and_limits(self):
        for src, expected in [("jmp 0", 0xD000), ("JMP 0xFFF", 0xDFFF),
                              ("JMP 4095", 0xDFFF), ("LDI R3,-128", 0x4C80),
                              ("LDI R0,255", 0x40FF), ("LDI R0,0b101 # x", 0x4005),
                              ("WORD 0xFFFF", 0xFFFF), (".word 0", 0),
                              ("NOP", 0x8000), ("NOP R2 R3", 0x82C0),
                              ("hlt ; stop", 0xC000)]:
            with self.subTest(src=src):
                self.assertEqual(writer.assemble_line(src), expected)
        for src in ["JMP -1", "JMP 0x1000", "JMP", "JMP R0", "LDI R0,256",
                    "LDI R0,-129", "MOV R4,R0", "MOV R0", "HLT R0",
                    "WORD 0840", "WORD -1", "WORD 0x10000", "JZ 0", "JNZ 0"]:
            with self.subTest(src=src), self.assertRaises(ValueError):
                writer.assemble_line(src)

    def test_decode_round_trip_all_words(self):
        self.assertEqual(writer.word_to_asm_hint(0xD004), "JMP 0x004")
        self.assertEqual(writer.word_to_asm_hint(0xE000), "WORD 0xE000")
        for word in range(0x10000):
            self.assertEqual(writer.assemble_line(writer.word_to_asm_hint(word)), word)


class ListingTests(unittest.TestCase):
    def test_listing_and_ram_rows(self):
        program = instructions("MOV R0, R1", *(["NOP"] * 15), "JMP 0xFFF")
        result = writer.render_listing(program)
        self.assertIn("0x000 0011 0001 0100 0000  # 3140  MOV R0, R1", result)
        rows = [line.split("\t") for line in result.splitlines() if "\t" in line]
        self.assertEqual([row[0] for row in rows], ["0x000", "0x010"])
        self.assertTrue(all(len(row) == 17 for row in rows))
        self.assertEqual(rows[1][1:], ["0xDFFF"] + ["0xC000"] * 15)

    def test_empty_full_and_overflow(self):
        empty_row = writer.render_listing([]).splitlines()[-1].split("\t")
        self.assertEqual(empty_row, ["0x000"] + ["0xC000"] * 16)
        full = instructions(*(["NOP"] * 4096))
        result = writer.render_listing(full)
        self.assertIn("0xFFF 1000 0000 0000 0000", result)
        rows = [line for line in result.splitlines() if "\t" in line]
        self.assertEqual(len(rows), 256)
        self.assertTrue(rows[-1].startswith("0xFF0\t"))
        with self.assertRaises(ValueError):
            writer.render_listing(full + instructions("HLT"))

    def test_repl_reset_delete_errors_and_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test program.lst"
            output = run_repl(["LDI R0, 7", "/start", "# comment", "JMP 0x1000",
                               "MOV R1, R2", "HLT", "/delete", "/show",
                               f'/save "{path.with_suffix(".asm")}"', "/exit"])
            saved = path.read_text(encoding="utf-8")
            self.assertIn("0x000 0011 0110 1000 0000  # 3680  MOV R1, R2", saved)
            self.assertNotIn("LDI", saved)
            self.assertNotIn("0x001 ", saved)
            self.assertIn("错误：", output)
            self.assertFalse(path.with_suffix(".asm").exists())
            self.assertIn("=> 0x000", output)

    def test_repl_capacity_and_delete_from_full(self):
        output = run_repl([*(["NOP"] * 4096), "HLT", "/delete", "JMP 0", "/exit"])
        self.assertIn("RAM 已满", output)
        self.assertIn("=> 0xFFF 1101 0000 0000 0000  # D000  JMP 0", output)
        self.assertNotIn("=> 0x1000", output)

    def test_startup_help_grouped_and_chinese(self):
        output = run_repl(["/exit"])
        self.assertIn("v0.2", output.splitlines()[0])
        for text in ["汇编指令", "输入规则", "交互命令", "复制：Rd = Rs",
                     "跳转到指定字地址", "/save [文件名]"]:
            self.assertIn(text, output)


if __name__ == "__main__":
    unittest.main()
