#!/bin/bash
# =============================================================================
#  MyDAPLink_F103 构建脚本  (Windows + Git Bash)
# =============================================================================
#  为什么需要这个包装脚本（和官方直接 make 有什么不同）：
#
#  1) progen 生成的 Makefile 会直接执行裸 `.py` 文件（不带 python 前缀），
#     Windows 下依赖文件关联；在 Git Bash 里会失效并被吞成 "make error 193"。
#     因此本脚本分两段跑：
#        阶段 1  progen_compile.py  —— 生成 Makefile 并编译（产出 elf/hex/bin）
#        阶段 2  post_build_script_gcc.py —— 显式用 venv python 跑 CRC 打包
#                                     （这一步才产出 *_crc.hex/*_crc.bin）
#
#  2) project_generator 会把 ARM_GCC_PATH 原样写进 Makefile 的 TOOLCHAIN_BINPATH，
#     既缺尾部反斜杠又含空格且未加引号 → sh 语法错误。必须 export 为空，
#     让 make 从 PATH 找 arm-none-eabi-gcc。
#
#  用法:
#      ./build.sh bl        # 编 bootloader   (stm32f103xb_bl)
#      ./build.sh if        # 编 interface    (stm32f103xb_if, 通用 target + USB bulk)
#      ./build.sh if-rb     # 编 interface    (stm32f103xb_stm32f103rb_if)
#      ./build.sh <原始工程名>   # 也可直接传 projects.yaml 里的工程名
# =============================================================================

set -u

PKG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAP_ROOT="$PKG_ROOT/src/upstream"
VENV_PY="$PKG_ROOT/.venv/Scripts/python.exe"
TOOLCHAIN="make_gcc_arm"

# ---- 工程名别名 -------------------------------------------------------------
case "${1:-}" in
    bl)     PROJECT="stm32f103xb_bl" ;;
    if)     PROJECT="stm32f103xb_if" ;;
    if-rb)  PROJECT="stm32f103xb_stm32f103rb_if" ;;
    "")     echo "用法: ./build.sh <bl|if|if-rb|工程名>"; exit 1 ;;
    *)      PROJECT="$1" ;;
esac

if [ ! -x "$VENV_PY" ]; then
    echo "!!! 找不到 venv: $VENV_PY"
    echo "!!! 请先执行: python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -r src/upstream/requirements.txt"
    exit 1
fi

export ARM_GCC_PATH=''

# 本机没有系统级 make，使用包内便携版 tools/bin/make.exe（GNU Make 4.4.1）
if [ -x "$PKG_ROOT/tools/bin/make.exe" ]; then
    export PATH="$PKG_ROOT/tools/bin:$PATH"
fi
if ! command -v make >/dev/null 2>&1; then
    echo "!!! 找不到 make。请把 GNU make 放到 $PKG_ROOT/tools/bin/make.exe"
    exit 1
fi

echo "=============================================="
echo " MyDAPLink_F103 build"
echo " project    : $PROJECT"
echo " toolchain  : $TOOLCHAIN"
echo " DAP_ROOT   : $DAP_ROOT"
echo "=============================================="

cd "$DAP_ROOT" || exit 1

# ---- 阶段 1 ----------------------------------------------------------------
"$VENV_PY" tools/progen_compile.py "$PROJECT" --toolchain "$TOOLCHAIN"
PROGEN_RC=$?

PROJ_DIR="projectfiles/$TOOLCHAIN/$PROJECT"
echo ""
echo "--- progen rc=$PROGEN_RC ; 检查产物 ---"
ls -la "$PROJ_DIR"/build/*.hex "$PROJ_DIR"/build/*.bin 2>/dev/null \
  || echo "(未产出 hex/bin，继续走 post_build 看是否能补)"
echo ""

if [ ! -d "$PROJ_DIR" ]; then
    echo "!!! $PROJ_DIR 不存在 —— 工程名可能写错。"
    echo "!!! 合法工程名: grep -n 'stm32f103' $DAP_ROOT/projects.yaml"
    exit 1
fi

# ---- 阶段 2 ----------------------------------------------------------------
echo "--- post_build_script_gcc.py (CRC 打包) ---"
( cd "$PROJ_DIR" && "$VENV_PY" "$DAP_ROOT/tools/post_build_script_gcc.py" )
echo "post_build rc=$?"

echo ""
echo "--- 最终产物 ---"
ls -la "$PROJ_DIR"/build/*_crc.hex "$PROJ_DIR"/build/*_crc.bin 2>/dev/null || {
    echo "!!! _crc 产物缺失，编译未完成。"
    exit 1
}

echo ""
echo "CRC 校验:"
for f in "$PROJ_DIR"/build/*_crc.hex; do
    echo -n "  $(basename "$f")  "
    "$VENV_PY" -c "
import sys,zlib
d=open(sys.argv[1],'rb').read()
print('crc32=0x%08x  size=%d' % (zlib.crc32(d)&0xffffffff, len(d)))
" "$f"
done

echo ""
echo "产物目录: $PROJ_DIR/build/"
echo "记得把 *_crc.hex 复制到 $PKG_ROOT/out/"
