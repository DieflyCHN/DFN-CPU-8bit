# DFN-CPU ISA 1.0
## Basic Info
CPU Version:			V0.2
CPU bit width:		8 bits
Register:					4 x 8 bits
Instruction width:	16 bits

RAM size:		8 KiB (4096 x 16 bits)
RAM Range:		0x000 - 0xFFF

## ISA Details
15-14: TYPE
	00 ALU
	01 LDI
	10 READ/NOP
	11 HLT/JMP

### ALU MODE (00)
13-12: OP
	00 ADD
	01 SUB
	10 AND (bit logic)
	11 OR  (bit logic)
11-10: WA (Write Addr)
09-08: RA (Read Addr A)
07-06: RB (Read Addr B)
05-00: 000000

###  LDI MODE (01)
13-12: 00
11-10: WA (Write Addr)
09-08: 00
07-00: Number (0-255)

### READ MODE (10)
13-10: 0000
09-08: RA (Read Addr A)
07-06: RB (Read Addr B)
05-00: 000000

### HLT/JMP MODE (11)
13-12: OP
	00 HLT
	01 JMP addr
	10 JZ addr (not realized)
	11 JNZ addr (not realized)
11-00: Addr

### MOV pseudo-instruction
`MOV Rd, Rs` 等价于 `OR Rd, Rs, Rs`，占一个 16 位指令字，无新增硬件操作码。
例如：`MOV R0, R1` → `0x3140`；`MOV R1, R2` → `0x3680`。

## ROM Writer v0.2
运行 `python3 rom_writer_v0.2.py` 进入实时输入模式；启动时按汇编指令、输入规则和交互命令分组显示中文说明。
容量与 CPU v0.2 同步：4096 个 16 位字，字地址 `0x000–0xFFF`。提示符为下一条指令地址，成功回显为当前指令地址。

支持 `LDI`、`ADD/SUB/AND/OR`、`MOV`、`READ`、`NOP`、`HLT`、`JMP Addr` 和 `WORD 0x1234`。
目标寄存器在前，寄存器范围 R0–R3。`LDI` 接受 -128–255（负数按 8 位补码编码）；地址只接受 0–4095。
数字默认十进制，十六进制必须带 `0x`，二进制带 `0b`，如 `WORD 0x0840`；不接受 `WORD 0840`。
指令大小写不限，逗号可省略，`;` 或 `#` 开始注释；纯注释行不占地址。`NOP Ra, Rb` 保留为 `READ Ra, Rb` 的兼容写法。
`JZ/JNZ` 尚未实现，不接受对应助记符；原始机器码可用 `WORD` 输入。

`/start` 清空程序；`/show` 显示列表；`/delete` 删除末条并回退地址；`/help` 显示说明；`/exit` 退出。
`/save` 仅保存 `program.lst`；`/save 名称` 保存为 `.lst` 文件，提供其他扩展名时替换为 `.lst`。含空格的路径请加双引号。
列表前半部分采用下例的地址、二进制、机器码及汇编格式，保留输入的助记符（包括 MOV）。尾部为 RAM 复制区，每行以 `0x000`、`0x010` 等字地址开头，随后 16 个 `0xNNNN`，字段用制表符分隔。
复制时只选取 RAM 复制区的数据行。仅输出程序覆盖的行，末行空位填 `HLT = 0xC000`；空程序输出一行 16 个 HLT。其余 RAM 地址不在输出范围内。

## Example: Fibonacci sequence
0x000 0100 0000 0000 0000  # 4000  LDI R0, 0
0x001 0100 0100 0000 0001  # 4401  LDI R1, 1
0x002 0100 1000 0000 0000  # 4800  LDI R2, 0
0x003 0100 1100 0000 0000  # 4C00  LDI R3, 0
0x004 0000 1000 0100 0000  # 0840  ADD R2, R0, R1
0x005 0011 0001 0100 0000  # 3140  MOV R0, R1
0x006 0011 0110 1000 0000  # 3680  MOV R1, R2
0x007 1000 0010 1100 0000  # 82C0  READ R2, R3
0x008 1101 0000 0000 0100  # D004  JMP 0x004

0x000	0x4000	0x4401	0x4800	0x4C00	0x0840	0x3140	0x3680	0x82C0	0xD004	0xC000	0xC000	0xC000	0xC000	0xC000	0xC000	0xC000

