# DFN-CPU ISA 1.0
## Basic Info
CPU Version:			V0.2
CPU bit width:		8 bits
Register:					4 x 8 bits
Instruction width:	16 bits
ALU Flags:		Z, N, C, V (saved in a 4-bit register)

RAM size:		8 KiB (4096 x 16 bits)
RAM Range:		0x000 - 0xFFF

## ISA Details
15-14: TYPE
	00 ALU
	01 LDI
	10 ALU Immediate
	11 HLT/JMP/JZ/JNZ

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

### ALU Immediate (10)
13-12: OP
	00 ADDI
	01 SUBI
	10 ANDI (bit logic)
	11 ORI  (bit logic)
11-10: WA (Write Addr)
09-08: RA (Read Addr A)
07-00: IMM8 (8 bit)

用法为 `ADDI/SUBI/ANDI/ORI Rd, Ra, imm8`，第二个源操作数为 IMM8，不再使用 RB。
例如：`ADDI R0, R0, 1` → `0x8001`；`SUBI R0, R0, 1` → `0x9001`；
`ANDI R2, R0, 1` → `0xA801`；`ORI R0, R0, 1` → `0xB001`。

### HLT/JMP MODE (11)
13-12: OP
	00 HLT
	01 JMP addr
	10 JZ addr
	11 JNZ addr
11-00: Addr

`HLT` 固定编码 `0xC000`。`JMP/JZ/JNZ` 的低 12 位是绝对字地址，范围 `0x000–0xFFF`。
`JZ` 在锁存的 Z=1 时跳转，`JNZ` 在锁存的 Z=0 时跳转；条件不成立时 PC 正常递增。

### Datapath and Flags

在 ALU.B 前增加一个 8-bit MUX，以 TYPE=10 选择立即数 ED；ALU 本身无需修改。

```ini
IMM = (TYPE == 10)
LEE = (TYPE == 01)
ALU.B = IMM ? ED : RegisterFile.B
WD = LEE ? ED : ALU.Y
WE = (TYPE != 11)
FlagWriteEnable = NOT IR[14]
```

4-bit Flags 寄存器在指令执行对应的时钟沿锁存 ALU 的 Z、N、C、V。
TYPE=00、10 更新 Flags；TYPE=01、11 保持 Flags。
条件跳转读取寄存器保存的 Z，不读取 ALU 的实时组合输出。

```ini
HLT = (IR[15:12] == 0xC)
JMP = (IR[15:12] == 0xD)
JZ  = (IR[15:12] == 0xE)
JNZ = (IR[15:12] == 0xF)
PC.ld = JMP OR (JZ AND Z_saved) OR (JNZ AND NOT Z_saved)
PC.D = IR[11:0]
PC.en = RUN AND NOT HLT
```

### MOV pseudo-instruction
`MOV Rd, Rs` 等价于 `OR Rd, Rs, Rs`，占一个 16 位指令字，无新增硬件操作码。
例如：`MOV R0, R1` → `0x3140`；`MOV R1, R2` → `0x3680`。
MOV 与 OR 一样更新 Flags。

### Encoding compatibility
ADD、SUB、AND、OR、LDI、MOV、HLT、JMP 的编码保持不变。
READ 已取消，原 TYPE=10 空间全部改作立即数运算。旧 NOP 的 `0x8000` 现为 `ADDI R0, R0, 0`，会写回并更新 Flags，不能再用作旧 NOP。
汇编器拒绝 READ 和 NOP，避免旧程序被静默编码为新指令。旧 READ 的机器码也必须迁移。

## ROM Writer v0.2
运行 `python3 rom_writer_v0.2.py` 进入实时输入模式；启动时按汇编指令、输入规则和交互命令分组显示中文说明。
容量与 CPU v0.2 同步：4096 个 16 位字，字地址 `0x000–0xFFF`。提示符为下一条指令地址，成功回显为当前指令地址。

支持 `LDI`、`ADD/SUB/AND/OR`、`ADDI/SUBI/ANDI/ORI`、`MOV`、`HLT`、`JMP/JZ/JNZ Addr` 和 `WORD 0x1234`。
目标寄存器在前，寄存器范围 R0–R3。`LDI` 和立即数 ALU 接受 -128–255（负数按 8 位补码编码）；地址只接受 0–4095。
数字默认十进制，十六进制必须带 `0x`，二进制带 `0b`，如 `WORD 0x0840`；不接受 `WORD 0840`。
指令大小写不限，逗号可省略，`;` 或 `#` 开始注释；纯注释行不占地址。
不支持标签语法；JMP/JZ/JNZ 必须指定绝对地址。原始机器码可用 `WORD` 输入。

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
0x007 1101 0000 0000 0100  # D004  JMP 0x004

0x000	0x4000	0x4401	0x4800	0x4C00	0x0840	0x3140	0x3680	0xD004	0xC000	0xC000	0xC000	0xC000	0xC000	0xC000	0xC000	0xC000

## Example: Countdown with saved Z

LDI 不修改 Flags。SUBI 更新 Z，JNZ 根据保存的 Z 决定是否回到 0x001；R0 减到 0 后执行 HLT。

```text
0x000 0100 0000 0000 0011  # 4003  LDI R0, 3
0x001 1001 0000 0000 0001  # 9001  SUBI R0, R0, 1
0x002 1111 0000 0000 0001  # F001  JNZ 0x001
0x003 1100 0000 0000 0000  # C000  HLT
```
0x000	0x4003	0x9001	0xF001	0xC000	0x0000	0x0000	0x0000	0x0000	0x0000	0x0000	0x0000	0x0000	0x0000	0x0000	0x0000	0x0000
